from collections import defaultdict, deque
from typing import Dict, Set
import random
import time

from django.db import transaction

from core.models import (
    DefaultTimetable,
    PeriodSlot,
    TeacherClassAssignment,
    Class,
)


class ScheduleReport:
    def __init__(self):
        self.placed = 0
        self.skipped = 0
        self.reason_counts = defaultdict(int)

    def add_placed(self):
        self.placed += 1

    def add_skipped(self, reason: str):
        self.skipped += 1
        self.reason_counts[reason] += 1

    def as_dict(self):
        return {
            "placed": self.placed,
            "skipped": self.skipped,
            "reasons": dict(self.reason_counts),
        }


def _day_list():
    return [d[0] for d in DefaultTimetable.DAY_CHOICES]


def generate_timetable(*, overwrite: bool = True, seed: int | None = None) -> Dict:
    """Generate a school timetable using TeacherClassAssignment and Subject.weekly_lessons.

    Rules:
    - Overwrite existing timetable when overwrite=True.
    - No teacher double-booked in the same period.
    - One subject per class/period.
    - Distribute lessons evenly across the week by iterating day->period->class.
    """
    report = ScheduleReport()

    # Periods and days
    periods_ordered = list(PeriodSlot.objects.filter(is_class_slot=True).order_by("start_time"))
    periods = list(periods_ordered)
    days = _day_list()

    # Randomizer for uniqueness per run
    rng = random.Random(seed if seed is not None else int(time.time() * 1000) & 0x7FFFFFFF)

    # Build demand: for each class, subject, teacher -> number of weekly lessons (from subject.weekly_lessons)
    assignments = (
        TeacherClassAssignment.objects
        .select_related("teacher__user", "class_group", "subject")
        .order_by("class_group__level", "class_group__name", "subject__name")
    )

    # Priority subjects by name (case-insensitive)
    PRIORITY_SUBJECTS: Set[str] = {"mathematics", "english", "kiswahili"}

    # Map class -> list of (subject_id, teacher_id, remaining_count)
    class_demands: Dict[int, deque] = defaultdict(deque)
    # Track which subject ids are priority for quick checks
    priority_subject_ids: Set[int] = set()
    math_subject_ids: Set[int] = set()
    total_required = 0
    for a in assignments:
        # Enforce minimum of 3 lessons per subject per week
        count = max(3, int(getattr(a.subject, "weekly_lessons", 3)))
        subj_name = (getattr(a.subject, 'name', '') or '').strip().lower()
        is_priority = subj_name in PRIORITY_SUBJECTS
        if is_priority:
            priority_subject_ids.add(a.subject_id)
            # Must appear every day: ensure at least len(days) lessons
            # (still can exceed if weekly_lessons > days)
            # Will be enforced after we know days; temporarily store, fix below
        if subj_name == "mathematics":
            math_subject_ids.add(a.subject_id)
        if count <= 0:
            continue
        class_demands[a.class_group_id].append([a.subject_id, a.teacher_id, count])
        total_required += count

    classes = list(Class.objects.all().order_by("level", "name"))

    if overwrite:
        DefaultTimetable.objects.all().delete()

    # Shuffle orders to improve uniqueness
    rng.shuffle(days)
    rng.shuffle(periods)
    rng.shuffle(classes)

    # Preferred early periods for Mathematics: first 4 by start_time (soft preference)
    early_periods = periods_ordered[:4]
    late_periods = [p for p in periods_ordered if p not in early_periods]

    # After knowing days, raise priority demands to at least number of days
    for class_id, dq in class_demands.items():
        newdq = deque()
        for subj_id, teacher_id, cnt in dq:
            if subj_id in priority_subject_ids:
                cnt = max(cnt, len(days))
            newdq.append([subj_id, teacher_id, cnt])
        class_demands[class_id] = newdq

    # Busy maps
    teacher_busy = set()  # (teacher_id, day, period_id)
    class_busy = set()    # (class_id, day, period_id)
    # Track counts per class/subject/day to avoid clustering a subject on the same day
    class_subject_day_count: Dict[tuple, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # Track per (class, day) which priority subject (if any) has already been allowed to repeat
    repeating_priority_subject: Dict[tuple, int | None] = {}

    # Strategy:
    # 1) Seed pass: ensure each priority subject appears at least once per day for each class (if possible)
    # 2) General fill: same as before, but allow multiple per day for priority subjects
    with transaction.atomic():
        # 1) Seeding
        for c in classes:
            dq = class_demands[c.id]
            if not dq:
                continue
            # Build quick lookup of items by subject
            items = list(dq)
            # For each day, try to place one period for each priority subject
            for day in days:
                for subj_id, teacher_id, remaining in list(items):
                    if subj_id not in priority_subject_ids or remaining <= 0:
                        continue
                    # if already placed today skip
                    if class_subject_day_count[(c.id, subj_id)][day] > 0:
                        continue
                    # find free period
                    placed_seed = False
                    # Prefer early periods for Mathematics, otherwise use general order
                    preferred_list = []
                    if subj_id in math_subject_ids:
                        early = early_periods[:]
                        late = late_periods[:]
                        rng.shuffle(early)
                        rng.shuffle(late)
                        preferred_list = early + late
                    else:
                        # use ordered-by-time but shuffled copy for variety
                        preferred_list = periods_ordered[:]
                        rng.shuffle(preferred_list)
                    for period in preferred_list:
                        key_c = (c.id, day, period.id)
                        if key_c in class_busy:
                            continue
                        if (teacher_id, day, period.id) in teacher_busy:
                            continue
                        # place
                        DefaultTimetable.objects.create(
                            class_group_id=c.id,
                            subject_id=subj_id,
                            period=period,
                            day=day,
                            teacher_id=teacher_id,
                        )
                        teacher_busy.add((teacher_id, day, period.id))
                        class_busy.add(key_c)
                        class_subject_day_count[(c.id, subj_id)][day] += 1
                        report.add_placed()
                        # decrement in deque
                        # rotate until we find this subject at head
                        for _ in range(len(dq)):
                            if dq[0][0] == subj_id and dq[0][1] == teacher_id:
                                break
                            dq.rotate(-1)
                        if dq and dq[0][0] == subj_id and dq[0][1] == teacher_id:
                            head = dq.popleft()
                            head[2] -= 1
                            if head[2] > 0:
                                dq.append(head)
                        placed_seed = True
                        break
                    # next subject
        # 2) General fill with preference against clustering for non-priority subjects
        for day in days:
            for period in periods:
                for c in classes:
                    key_c = (c.id, day, period.id)
                    if key_c in class_busy:
                        continue
                    if not class_demands[c.id]:
                        continue
                    placed = False
                    fallback_idx = None
                    qlen = len(class_demands[c.id])
                    for idx in range(qlen):
                        subj_id, teacher_id, remaining = class_demands[c.id][0]
                        # Teacher busy -> rotate
                        if (teacher_id, day, period.id) in teacher_busy:
                            class_demands[c.id].rotate(-1)
                            continue
                        prior_count_today = class_subject_day_count[(c.id, subj_id)][day]
                        # For non-priority subjects, prefer not repeating same day
                        if (subj_id not in priority_subject_ids) and prior_count_today > 0:
                            # keep as fallback but try others first
                            if fallback_idx is None:
                                fallback_idx = idx
                            class_demands[c.id].rotate(-1)
                            continue
                        # For priority subjects: allow multiple per day, but only one priority subject may repeat per class/day
                        if (subj_id in priority_subject_ids) and prior_count_today > 0:
                            rp_key = (c.id, day)
                            rp = repeating_priority_subject.get(rp_key)
                            if rp is not None and rp != subj_id:
                                # another priority subject already repeating today -> skip/try others
                                class_demands[c.id].rotate(-1)
                                continue
                        # Place
                        DefaultTimetable.objects.create(
                            class_group_id=c.id,
                            subject_id=subj_id,
                            period=period,
                            day=day,
                            teacher_id=teacher_id,
                        )
                        teacher_busy.add((teacher_id, day, period.id))
                        class_busy.add(key_c)
                        # Update day count and repeating-priority tracker
                        before = class_subject_day_count[(c.id, subj_id)][day]
                        class_subject_day_count[(c.id, subj_id)][day] = before + 1
                        if (subj_id in priority_subject_ids) and before >= 1:
                            # This subject is now repeating today; lock it as the only repeating priority subject for this class/day
                            repeating_priority_subject[(c.id, day)] = subj_id
                        report.add_placed()
                        remaining -= 1
                        class_demands[c.id].popleft()
                        if remaining > 0:
                            class_demands[c.id].append([subj_id, teacher_id, remaining])
                        placed = True
                        break
                    if not placed and fallback_idx is not None:
                        # Fallback only allowed for priority subjects repeating same day.
                        subj_id, teacher_id, remaining = class_demands[c.id][0]
                        prior_count_today = class_subject_day_count[(c.id, subj_id)][day]
                        if (subj_id not in priority_subject_ids) and prior_count_today > 0:
                            # Do not allow non-priority repeats within the same day
                            class_demands[c.id].rotate(-1)
                        elif (teacher_id, day, period.id) in teacher_busy:
                            class_demands[c.id].rotate(-1)
                        else:
                            DefaultTimetable.objects.create(
                                class_group_id=c.id,
                                subject_id=subj_id,
                                period=period,
                                day=day,
                                teacher_id=teacher_id,
                            )
                            teacher_busy.add((teacher_id, day, period.id))
                            class_busy.add(key_c)
                            class_subject_day_count[(c.id, subj_id)][day] += 1
                            report.add_placed()
                            remaining -= 1
                            class_demands[c.id].popleft()
                            if remaining > 0:
                                class_demands[c.id].append([subj_id, teacher_id, remaining])
                    elif not placed and class_demands[c.id]:
                        report.add_skipped("no_slot_found_or_teacher_busy")

    return report.as_dict()

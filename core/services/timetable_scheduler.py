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
        # diagnostics
        self.meta = {
            "classes": {}
        }

    def add_placed(self):
        self.placed += 1

    def add_skipped(self, reason: str):
        self.skipped += 1
        self.reason_counts[reason] += 1

    def set_class_meta(self, class_id: int, *, capacity: int, demand_original: int, demand_adjusted: int):
        self.meta["classes"][class_id] = {
            "capacity": capacity,
            "demand_original": demand_original,
            "demand_adjusted": demand_adjusted,
            "oversubscribed": demand_original > capacity,
        }

    def as_dict(self):
        return {
            "placed": self.placed,
            "skipped": self.skipped,
            "reasons": dict(self.reason_counts),
            "meta": self.meta,
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

    # Build demand: for each class, subject, teacher -> number of weekly lessons
    # Exclude component (child) subjects from scheduling
    assignments = (
        TeacherClassAssignment.objects
        .select_related("teacher__user", "class_group", "subject")
        .filter(subject__part_of__isnull=True)
        .order_by("class_group__level", "class_group__name", "subject__name")
    )

    # Priority subjects by name (case-insensitive)
    PRIORITY_SUBJECTS: Set[str] = {"mathematics", "english", "kiswahili"}

    # Map class -> list of (subject_id, teacher_id, remaining_count)
    class_demands: Dict[int, deque] = defaultdict(deque)
    # Map class -> set of (subject_id, teacher_id) from assignments for final fill
    class_pairs: Dict[int, Set[tuple]] = defaultdict(set)
    # Track which subject ids are priority for quick checks
    priority_subject_ids: Set[int] = set()
    math_subject_ids: Set[int] = set()
    total_required = 0
    for a in assignments:
        # Enforce minimum lessons per subject per week using Subject.min_weekly_lessons
        min_lessons = int(getattr(a.subject, "min_weekly_lessons", 3) or 3)
        target_lessons = int(getattr(a.subject, "weekly_lessons", min_lessons) or min_lessons)
        count = max(min_lessons, target_lessons)
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
        class_pairs[a.class_group_id].add((a.subject_id, a.teacher_id))
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

    # Capacity-aware normalization (do NOT inflate priorities to days)
    # Compute per-class capacity and trim demand to fit capacity, reducing non-priority first.
    periods_per_day = len(periods)
    days_per_week = len(days)
    # Build quick lookups for subject priority
    is_priority_id = lambda sid: sid in priority_subject_ids

    # Enforce daily presence target for priority subjects by ensuring
    # their requested weekly count is at least the number of school days.
    # This happens BEFORE capacity normalization so non-priority demand
    # is preferentially trimmed when oversubscribed.
    for cid, dq in class_demands.items():
        # dq contains [subject_id, teacher_id, count]
        for i in range(len(dq)):
            subj_id, teacher_id, cnt = dq[i]
            if is_priority_id(subj_id) and cnt < days_per_week:
                dq[i][2] = days_per_week
    for c in Class.objects.all():
        dq = class_demands.get(c.id, deque())
        # original demand
        demand_original = sum(item[2] for item in dq)
        capacity = periods_per_day * days_per_week
        if demand_original <= capacity or not dq:
            # record meta and continue
            report.set_class_meta(c.id, capacity=capacity, demand_original=demand_original, demand_adjusted=demand_original)
            continue
        # Separate into priority and non-priority buckets
        pr_items = []
        non_items = []
        for subj_id, teacher_id, cnt in dq:
            (pr_items if is_priority_id(subj_id) else non_items).append([subj_id, teacher_id, cnt])
        # Start with original counts; then reduce non-priority first, one-by-one, largest-first
        def total_count(lst):
            return sum(x[2] for x in lst)
        # Combine for manipulation
        pr_items.sort(key=lambda x: -x[2])
        non_items.sort(key=lambda x: -x[2])
        total = total_count(pr_items) + total_count(non_items)
        # Reduce non-priority first
        while total > capacity and non_items:
            non_items.sort(key=lambda x: -x[2])
            if non_items[0][2] > 0:
                non_items[0][2] -= 1
                total -= 1
            else:
                non_items.pop(0)
        # If still over capacity, reduce priority as last resort but keep at least 1 per subject
        while total > capacity and pr_items:
            pr_items.sort(key=lambda x: -x[2])
            if pr_items[0][2] > 1:
                pr_items[0][2] -= 1
                total -= 1
            else:
                # cannot reduce below 1; move to next
                # remove items that hit 1 only if all are at 1 and still over; then allow zero
                # safeguard to break infinite loop
                all_at_min = all(it[2] <= 1 for it in pr_items)
                if all_at_min:
                    pr_items[0][2] = max(0, pr_items[0][2] - 1)
                    total -= 1
                else:
                    # move smallest to end and keep reducing
                    pr_items.append(pr_items.pop(0))
        # Recompose deque with adjusted counts, dropping zeros
        newdq = deque()
        for lst in (pr_items, non_items):
            for subj_id, teacher_id, cnt in lst:
                if cnt > 0:
                    newdq.append([subj_id, teacher_id, cnt])
        class_demands[c.id] = newdq
        report.set_class_meta(c.id, capacity=capacity, demand_original=demand_original, demand_adjusted=sum(x[2] for x in newdq))

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
    # 3) Final fill: ensure at most 2 blanks per class for the week by repeating subjects if necessary
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
        # 2) General fill replaced with maximum matching per period to reduce conflicts/skips
        # Lightweight Kuhn matching per (day, period)
        for day in days:
            for period in periods:
                # Build candidate edges: class -> list of teacher options (with subject)
                class_ids = []
                edges = defaultdict(list)  # class_id -> list[(teacher_id, subject_id)] ordered by priority
                # teacher load map for the current day to prefer less-loaded teachers
                teacher_load_today = defaultdict(int)
                for t_id, d, _pid in list(teacher_busy):
                    if d == day:
                        teacher_load_today[t_id] += 1
                for c in classes:
                    key_c = (c.id, day, period.id)
                    if key_c in class_busy:
                        continue
                    if not class_demands[c.id]:
                        continue
                    class_ids.append(c.id)
                    # Prepare ordered options for this (class, day, period)
                    # Preference: math in early periods; then priority subjects; then others
                    # Also avoid repeating non-priority more than once per day if alternatives exist
                    options_priority = []
                    options_non_priority = []
                    # Look through the deque without mutating order
                    for subj_id, teacher_id, remaining in list(class_demands[c.id]):
                        if remaining <= 0:
                            continue
                        # Teacher must be free this (day, period)
                        if (teacher_id, day, period.id) in teacher_busy:
                            continue
                        prior_today = class_subject_day_count[(c.id, subj_id)][day]
                        entry = (teacher_id, subj_id)
                        if subj_id in math_subject_ids and period in early_periods:
                            # strongest preference
                            options_priority.insert(0, entry)
                        elif subj_id in priority_subject_ids:
                            options_priority.append(entry)
                        else:
                            # penalize repeats in same day by ordering later
                            if prior_today > 0:
                                options_non_priority.append(entry)
                            else:
                                options_non_priority.insert(0, entry)
                    # Bias teacher ordering by lower load today (stable by preference)
                    ordered = options_priority + options_non_priority
                    ordered.sort(key=lambda pair: teacher_load_today.get(pair[0], 0))
                    edges[c.id] = ordered

                # Run matching: teachers are the right-side nodes
                match_t_to_c: Dict[int, int] = {}  # teacher_id -> class_id
                # Keep which subject to use for (class, teacher)
                choose_subject: Dict[tuple, int] = {}

                def dfs(cid: int, seen: Set[int]) -> bool:
                    for teacher_id, subj_id in edges.get(cid, []):
                        if teacher_id in seen:
                            continue
                        seen.add(teacher_id)
                        if (teacher_id not in match_t_to_c) or dfs(match_t_to_c[teacher_id], seen):
                            match_t_to_c[teacher_id] = cid
                            choose_subject[(cid, teacher_id)] = subj_id
                            return True
                    return False

                # Process most-constrained classes first (fewest options)
                class_ids.sort(key=lambda cid: len(edges.get(cid, [])))
                for cid in class_ids:
                    dfs(cid, set())

                # Place all matches for this period
                for teacher_id, cid in list(match_t_to_c.items()):
                    subj_id = choose_subject.get((cid, teacher_id))
                    if subj_id is None:
                        continue
                    key_c = (cid, day, period.id)
                    if key_c in class_busy or (teacher_id, day, period.id) in teacher_busy:
                        continue
                    # Persist placement
                    DefaultTimetable.objects.create(
                        class_group_id=cid,
                        subject_id=subj_id,
                        period=period,
                        day=day,
                        teacher_id=teacher_id,
                    )
                    teacher_busy.add((teacher_id, day, period.id))
                    class_busy.add(key_c)
                    before = class_subject_day_count[(cid, subj_id)][day]
                    class_subject_day_count[(cid, subj_id)][day] = before + 1
                    if (subj_id in priority_subject_ids) and before >= 1:
                        repeating_priority_subject[(cid, day)] = subj_id
                    report.add_placed()
                    # Decrement remaining for this (class, subj, teacher)
                    dq = class_demands[cid]
                    # rotate until found
                    for _ in range(len(dq)):
                        if dq[0][0] == subj_id and dq[0][1] == teacher_id:
                            break
                        dq.rotate(-1)
                    if dq and dq[0][0] == subj_id and dq[0][1] == teacher_id:
                        head = dq.popleft()
                        head[2] -= 1
                        if head[2] > 0:
                            dq.append(head)
                # For any class still free this period and having demand, allow a controlled repeat for non-priority if teacher free
                for c in classes:
                    key_c = (c.id, day, period.id)
                    if key_c in class_busy:
                        continue
                    if not class_demands[c.id]:
                        continue
                    placed = False
                    for subj_id, teacher_id, remaining in list(class_demands[c.id]):
                        if (teacher_id, day, period.id) in teacher_busy:
                            continue
                        prior_today = class_subject_day_count[(c.id, subj_id)][day]
                        if (subj_id not in priority_subject_ids) and prior_today > 0:
                            # one non-priority repeat allowed as fallback
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
                            # decrement
                            dq = class_demands[c.id]
                            for _ in range(len(dq)):
                                if dq[0][0] == subj_id and dq[0][1] == teacher_id:
                                    break
                                dq.rotate(-1)
                            if dq and dq[0][0] == subj_id and dq[0][1] == teacher_id:
                                head = dq.popleft()
                                head[2] -= 1
                                if head[2] > 0:
                                    dq.append(head)
                            placed = True
                            break
                    if not placed and class_demands[c.id]:
                        # Attempt swap: free a needed teacher by moving their current lesson to another free period today
                        # 1) Build candidate teachers needed now (from demand list)
                        needed = [(subj_id, teacher_id) for subj_id, teacher_id, rem in list(class_demands[c.id]) if rem > 0]
                        swapped = False
                        for subj_id, teacher_id in needed:
                            # If teacher is not busy, we would have placed above
                            # Find which class currently uses this teacher now
                            # Query the existing placement row for this period/day/teacher
                            existing = DefaultTimetable.objects.filter(
                                teacher_id=teacher_id,
                                day=day,
                                period=period,
                            ).first()
                            if not existing:
                                continue
                            other_cid = existing.class_group_id
                            other_subj_id = existing.subject_id
                            # Find another period p2 today where both (other_cid, teacher_id) are free
                            for p2 in periods:
                                if p2.id == period.id:
                                    continue
                                if (other_cid, day, p2.id) in class_busy:
                                    continue
                                if (teacher_id, day, p2.id) in teacher_busy:
                                    continue
                                # Perform swap: move existing to p2
                                existing.period = p2
                                existing.save(update_fields=["period"])
                                # Update busy maps
                                class_busy.discard((other_cid, day, period.id))
                                teacher_busy.discard((teacher_id, day, period.id))
                                class_busy.add((other_cid, day, p2.id))
                                teacher_busy.add((teacher_id, day, p2.id))
                                # Now place needed lesson for current class in freed slot
                                DefaultTimetable.objects.create(
                                    class_group_id=c.id,
                                    subject_id=subj_id,
                                    period=period,
                                    day=day,
                                    teacher_id=teacher_id,
                                )
                                teacher_busy.add((teacher_id, day, period.id))
                                class_busy.add((c.id, day, period.id))
                                class_subject_day_count[(c.id, subj_id)][day] += 1
                                report.add_placed()
                                # decrement current class demand
                                dq = class_demands[c.id]
                                for _ in range(len(dq)):
                                    if dq[0][0] == subj_id and dq[0][1] == teacher_id:
                                        break
                                    dq.rotate(-1)
                                if dq and dq[0][0] == subj_id and dq[0][1] == teacher_id:
                                    head = dq.popleft()
                                    head[2] -= 1
                                    if head[2] > 0:
                                        dq.append(head)
                                swapped = True
                                break
                            if swapped:
                                break
                        if not swapped:
                            report.add_skipped("no_match_for_period")

        # 3) Final fill pass: For each class, fill remaining blanks so that at most 2 remain
        for c in classes:
            # Build set of all (day, period.id) combos for this class
            all_keys = [(d, p) for d in days for p in periods]
            # Compute currently occupied
            occupied = {(day, period) for (cid, day, pid) in class_busy if cid == c.id for period in periods if period.id == pid}
            # Derive empty slots
            empty_slots = []
            for day in days:
                for period in periods:
                    if (c.id, day, period.id) not in class_busy:
                        empty_slots.append((day, period))
            # Only fill if more than 2 blanks
            idx = 0
            while len(empty_slots) - idx > 2:
                day, period = empty_slots[idx]
                key_c = (c.id, day, period.id)
                placed_any = False
                # Try priority subjects first, allowing multiple per day; then any subject
                # Build ordered candidate list
                priority_candidates = []
                non_priority_candidates = []
                for subj_id, teacher_id in class_pairs.get(c.id, set()):
                    if subj_id in priority_subject_ids:
                        priority_candidates.append((subj_id, teacher_id))
                    else:
                        non_priority_candidates.append((subj_id, teacher_id))
                candidates = priority_candidates + non_priority_candidates
                # Shuffle lightly for variety but deterministic per rng
                rng.shuffle(candidates)
                for subj_id, teacher_id in candidates:
                    if (teacher_id, day, period.id) in teacher_busy:
                        continue
                    # Place regardless of per-day repeat counts (we allow repeats here)
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
                    placed_any = True
                    break
                if not placed_any:
                    # Could not place due to teacher conflicts -> keep blank and count reason
                    report.add_skipped("final_fill_no_candidate")
                    idx += 1
                else:
                    # Successfully filled this slot, move to next remaining index without incrementing idx
                    idx += 1

    return report.as_dict()

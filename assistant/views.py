from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from urllib.parse import quote
import difflib
import re

from .models import BotSession, BotMessage, BotActionLog


def _best_fuzzy(token: str, options: set[str] | list[str], cutoff: float = 0.78):
    token = (token or '').strip().lower()
    if not token:
        return None
    opts = list(options)
    match = difflib.get_close_matches(token, opts, n=1, cutoff=cutoff)
    return match[0] if match else None


def _fuzzy_find_in_text(text: str, options: set[str] | list[str], cutoff: float = 0.78):
    """Try to find any option approximately within the text (checks uni/bi/tri-grams). Returns the matched canonical option or None."""
    t = (text or '').lower()
    # tokens of letters/numbers
    tokens = re.findall(r"[a-z0-9']+", t)
    grams = []
    # unigrams
    grams.extend(tokens)
    # bigrams and trigrams
    for i in range(len(tokens)-1):
        grams.append(tokens[i] + ' ' + tokens[i+1])
    for i in range(len(tokens)-2):
        grams.append(tokens[i] + ' ' + tokens[i+1] + ' ' + tokens[i+2])
    # Try exact contains first
    for opt in options:
        if opt in t:
            return opt
    # Fuzzy over grams
    best = None
    best_score = 0.0
    for g in grams:
        for opt in options:
            s = difflib.SequenceMatcher(None, g, opt).ratio()
            if s > best_score and s >= cutoff:
                best = opt
                best_score = s
    return best

def _detect_format_word(text: str):
    t = (text or '').lower()
    if any(w in t for w in ['bullet', 'bullets', 'list']):
        return 'bullets'
    if 'json' in t:
        return 'json'
    if 'table' in t:
        return 'table'
    if 'plain' in t or 'default' in t or 'normal' in t:
        return 'plain'
    return None

def _format_message(msg: str, fmt: str | None):
    if not fmt or fmt == 'plain':
        return msg
    if fmt == 'bullets':
        lines = [l.strip() for l in msg.split('\n') if l.strip()]
        return '\n'.join(f"- {l}" for l in lines)
    if fmt == 'json':
        import json
        try:
            return json.dumps({"message": msg}, ensure_ascii=False)
        except Exception:
            return msg
    if fmt == 'table':
        # Render a simple one-cell table with the message.
        return "| Message |\n|---|\n| " + msg.replace('\n', ' / ') + " |"
    return msg


def _resolve_class_by_text(text: str):
    """Return a (class_obj, name_match) by fuzzy matching against Class.name. None if not found or error."""
    try:
        from core.models import Class as ClassModel
        t = (text or '').strip().lower()
        # Fetch names once
        classes = list(ClassModel.objects.all().only('id', 'name'))
        if not classes:
            return None, None
        names = [c.name for c in classes]
        # Try direct contains first
        for c in classes:
            if c.name.lower() in t or t in c.name.lower():
                return c, c.name
        # Fuzzy over names
        match = _best_fuzzy(t, names, cutoff=0.72)
        if match:
            for c in classes:
                if c.name == match:
                    return c, match
    except Exception:
        return None, None
    return None, None

def _resolve_subject_by_text(text: str):
    """Return (subject_obj, name_match) by fuzzy matching against Subject.name."""
    try:
        from core.models import Subject as SubjectModel
        t = (text or '').strip().lower()
        subs = list(SubjectModel.objects.all().only('id', 'name'))
        if not subs:
            return None, None
        names = [s.name for s in subs]
        for s in subs:
            if s.name.lower() in t or t in s.name.lower():
                return s, s.name
        match = _best_fuzzy(t, names, cutoff=0.72)
        if match:
            for s in subs:
                if s.name == match:
                    return s, match
    except Exception:
        return None, None
    return None, None

def _resolve_exam_by_text(text: str):
    """Return (exam_obj, name_match) by fuzzy matching against Exam.name."""
    try:
        from core.models import Exam as ExamModel
        t = (text or '').strip().lower()
        exs = list(ExamModel.objects.all().only('id', 'name').order_by('-id'))
        if not exs:
            return None, None
        names = [e.name for e in exs]
        for e in exs:
            if e.name.lower() in t or t in e.name.lower():
                return e, e.name
        match = _best_fuzzy(t, names, cutoff=0.7)
        if match:
            for e in exs:
                if e.name == match:
                    return e, match
    except Exception:
        return None, None
    return None, None


@login_required(login_url='login')
def widget(request):
    return render(request, 'assistant/chat_widget.html')


def _ensure_session(user):
    session = BotSession.objects.filter(user=user, is_active=True).order_by('-last_activity').first()
    if not session:
        session = BotSession.objects.create(user=user)
    return session


def _intent_router(text: str, user):
    t = (text or '').strip().lower()
    # Basic intents (with fuzzy matching)
    if _best_fuzzy(t, {'help', 'menu'}):
        return 'help', {}
    # Greetings
    greetings = {'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'greetings'}
    if _fuzzy_find_in_text(t, greetings):
        return 'greet', {}
    # Broaden open intent triggers
    open_triggers = ['open ', 'go to ', 'navigate to ', 'show me ', 'take me to ']
    if t.startswith(tuple(open_triggers)) or any(difflib.SequenceMatcher(None, t[:len(p)], p).ratio() >= 0.8 for p in open_triggers):
        # e.g., "open analytics", "go to users"
        target = t.split(' ', 1)[1].strip() if ' ' in t else ''
        return 'open_page', {'target': target}
    # If user only types a known section name, treat as open_page
    single_word_triggers = {
        'dashboard','home','start','main',
        'analytics','reports','insights','stats',
        'users','accounts','staff',
        'messages','messaging','chat','inbox',
        'fees','payments','finance',
        'timetable','schedule','calendar',
        'attendance','rollcall','roll-call',
        'grades','upload grades','gradebook','marks','bulk grades','excel grades','manage grades','markbook',
        'profile','account',
        'classes','responsibilities',
        'teachers','students',
        'add student','new student','register student',
        'downloads','exports',
        'finance analytics','finance messaging',
        'overview','clerk overview',
        'website settings','gallery','categories',
        'subjects','subject components','academic years','period slots',
        'events','messaging admin','admin messaging',
        'payment','payment logs','payment history','mpesa reconcile',
        'attendance view','graduated students',
        'exam','exams','tests',
    }
    if t in single_word_triggers:
        return 'open_page', {'target': t}
    # Fuzzy: infer target from misspelled single-word inputs
    fuzzy_target = _fuzzy_find_in_text(t, single_word_triggers)
    if fuzzy_target:
        return 'open_page', {'target': fuzzy_target}
    # Set response format preferences
    if ('use ' in t or 'set ' in t or 'format' in t) and any(w in t for w in ['json','bullet','bullets','list','table','plain','default','normal']):
        fmt = _detect_format_word(t)
        if fmt:
            return 'set_response_format', {'format': fmt}
    # One-off inline format e.g. "in json" / "as bullets"
    inline_fmt = None
    for kw in [' in ', ' as ']:
        if kw in t:
            candidate = t.split(kw, 1)[1]
            f2 = _detect_format_word(candidate)
            if f2:
                inline_fmt = f2
                break
    # Export shortcuts: "export students pdf", "export teachers csv"
    if 'export' in t:
        return 'export_shortcut', {'query': t, 'respond_format': inline_fmt}
    # Class-aware intents: "class profile for 2 West", "result slip for Form 3 East"
    if 'class profile' in t and 'for' in t:
        after_for = t.split('for', 1)[1].strip()
        return 'open_class_profile', {'class_text': after_for, 'respond_format': inline_fmt}
    if ('result slip' in t or 'results for class' in t or 'results for' in t) and 'for' in t:
        after_for = t.split('for', 1)[1].strip()
        return 'open_class_result_slip', {'class_text': after_for, 'respond_format': inline_fmt}
    # Teacher-specific deep links
    if ('take attendance' in t or 'record attendance' in t) and 'for' in t:
        after_for = t.split('for', 1)[1].strip()
        return 'teacher_attendance_for', {'tail': after_for, 'respond_format': inline_fmt}
    if ('enter grades' in t or 'input grades' in t or 'upload grades' in t) and 'for' in t:
        after_for = t.split('for', 1)[1].strip()
        return 'teacher_input_grades_for', {'tail': after_for, 'respond_format': inline_fmt}
    if (('exam results' in t or 'results for' in t) and 'for' in t) or ('view results' in t and 'for' in t):
        after_for = t.split('for', 1)[1].strip()
        return 'teacher_exam_results_for', {'tail': after_for, 'respond_format': inline_fmt}
    # Results intents
    result_phrases = ['result slip', 'results for class', 'results', 'report card']
    if _fuzzy_find_in_text(t, result_phrases):
        # If student asks for results, open their own profile performance tab
        role = getattr(user, 'role', '') or ''
        if role == 'student':
            return 'student_results', {}
        # Otherwise, default to teacher class result slip for teachers
        if role == 'teacher':
            return 'teacher_result_slip', {}
        # Admin/others: fall back to help or dashboard
        return 'fallback', {}
    if any(k in t for k in ['record fee', 'payment']):
        return 'admin_record_payment', {}
    # Small-talk & FAQs
    if any(k in t for k in ['thank you', 'thanks', 'thx']):
        return 'smalltalk_thanks', {}
    if any(k in t for k in ["how are you", "how's it going", "how are u"]):
        return 'smalltalk_howareyou', {}
    if any(k in t for k in ['who are you', 'your name', 'who made you', 'what are you']):
        return 'smalltalk_about', {}
    if any(k in t for k in ['bye', 'goodbye', 'see you', 'later']):
        return 'smalltalk_bye', {}
    if any(k in t for k in ['reset password', 'change password', 'forgot password']):
        return 'faq_password', {}
    if any(k in t for k in ['contact support', 'helpdesk', 'report a bug', 'report issue', 'support']):
        return 'faq_support', {}
    if any(k in t for k in ['school hours', 'opening hours', 'office hours', 'when open']):
        return 'faq_hours', {}
    return 'fallback', {}


def _handle_intent(intent: str, slots: dict, request):
    user = request.user
    role = getattr(user, 'role', '') or ''
    # Role-aware routing
    if intent == 'greet':
        # Friendly greeting with role-aware suggestions
        base = "Hello! How can I help you today?"
        teacher_sugs = [
            {"text": "open timetable"},
            {"text": "attendance"},
            {"text": "gradebook"},
            {"text": "messages"},
        ]
        admin_sugs = [
            {"text": "open analytics"},
            {"text": "open users"},
            {"text": "open messages"},
        ]
        sugs = teacher_sugs if role == 'teacher' else (admin_sugs if role == 'admin' else [{"text": "open dashboard"}])
        return True, base, None, sugs

    if intent == 'help':
        msg = (
            "I can help with: \n"
            "- Open pages: analytics, users, messages, dashboard\n"
            "- Teacher: timetable, attendance, upload grades, gradebook, profile, classes\n"
            "- Admin: fees, exams (publish/manage)\n"
            "Tip: say ‘open timetable’ or ‘take me to gradebook’."
        )
        suggestions = [
            {"text": "open analytics"},
            {"text": "open messages"},
            {"text": "help"},
        ]
        return True, msg, None, suggestions

    # Small-talk handlers
    if intent == 'smalltalk_thanks':
        return True, "You're welcome!", None, [{"text": "help"}]
    if intent == 'smalltalk_howareyou':
        return True, "I'm here and ready to help!", None, [{"text": "open dashboard"}]
    if intent == 'smalltalk_about':
        return True, "I'm your in-app assistant for this School Management System. I can navigate and answer basic questions.", None, [
            {"text": "help"}, {"text": "open messages"}
        ]
    if intent == 'smalltalk_bye':
        return True, "Goodbye! Ping me anytime.", None, []

    # FAQs (generic, non-sensitive answers)
    if intent == 'faq_password':
        msg = (
            "To change your password: open your profile/account menu and choose Change Password. "
            "If you forgot it, use the Forgot Password link on the login page."
        )
        return True, msg, None, [{"text": "profile"}]
    if intent == 'faq_support':
        msg = (
            "For support: contact your system admin or use the Report Issue option if available in the top menu."
        )
        return True, msg, None, [{"text": "open dashboard"}]
    if intent == 'faq_hours':
        msg = (
            "School/office hours vary by institution. Please check the noticeboard or contact the office for exact times."
        )
        return True, msg, None, []

    if intent == 'open_page':
        target = (slots.get('target', '') or '').lower()
        # Resolve teacher id from Teacher model (not User id)
        tid = None
        if role == 'teacher':
            try:
                from core.models import Teacher
                t = Teacher.objects.filter(user=user).only('id').first()
                tid = t.id if t else None
            except Exception:
                tid = None
        # Define allowed targets with synonyms and role-aware URLs
        candidates = [
            # Teacher-friendly mapping for exam keywords to Gradebook
            { 'keys': {'exam','exams','tests'},
              'url': (f'/teacher/{tid}/gradebook/' if role == 'teacher' and tid else None),
              'allowed': {'teacher'}, 'label': 'Gradebook' },
            # Admin-specific quick links
            { 'keys': {'overview'},
              'url': '/admin_overview/', 'allowed': {'admin'}, 'label': 'Admin Overview' },
            { 'keys': {'clerk overview'},
              'url': '/clerk_overview/', 'allowed': {'clerk','admin'}, 'label': 'Clerk Overview' },
            { 'keys': {'website settings'},
              'url': '/admin_website_settings/', 'allowed': {'admin'}, 'label': 'Website Settings' },
            { 'keys': {'gallery'},
              'url': '/admin_gallery/', 'allowed': {'admin'}, 'label': 'Gallery' },
            { 'keys': {'categories'},
              'url': '/admin_categories/', 'allowed': {'admin'}, 'label': 'Categories' },
            { 'keys': {'teachers'},
              'url': '/admin_teachers/', 'allowed': {'admin'}, 'label': 'Admin Teachers' },
            { 'keys': {'students'},
              'url': '/admin_students/', 'allowed': {'admin'}, 'label': 'Admin Students' },
            { 'keys': {'add student','new student','register student'},
              'url': '/admin_students/', 'allowed': {'admin'}, 'label': 'Add Student' },
            { 'keys': {'graduated students'},
              'url': '/admin_graduated_students/', 'allowed': {'admin'}, 'label': 'Graduated Students' },
            { 'keys': {'classes'},
              'url': '/admin_classes/', 'allowed': {'admin'}, 'label': 'Admin Classes' },
            { 'keys': {'manage grades'},
              'url': '/admin_manage_grades/', 'allowed': {'admin'}, 'label': 'Admin Manage Grades' },
            { 'keys': {'subjects'},
              'url': '/admin_subjects/', 'allowed': {'admin'}, 'label': 'Subjects' },
            { 'keys': {'subject components'},
              'url': '/admin_subject_components/', 'allowed': {'admin'}, 'label': 'Subject Components' },
            { 'keys': {'academic years'},
              'url': '/admin_academic_years/', 'allowed': {'admin'}, 'label': 'Academic Years' },
            { 'keys': {'period slots'},
              'url': '/admin_period_slots/', 'allowed': {'admin'}, 'label': 'Period Slots' },
            { 'keys': {'finance analytics'},
              'url': '/finance/analytics/', 'allowed': {'admin','clerk'}, 'label': 'Finance Analytics' },
            { 'keys': {'finance messaging'},
              'url': '/finance_messaging/', 'allowed': {'admin','clerk'}, 'label': 'Finance Messaging' },
            { 'keys': {'downloads','exports'},
              'url': '/downloads/', 'allowed': {'admin'}, 'label': 'Downloads' },
            { 'keys': {'admin messaging','messaging admin'},
              'url': '/admin_messaging/', 'allowed': {'admin'}, 'label': 'Admin Messaging' },
            { 'keys': {'payment logs'},
              'url': '/admin_payment_logs/', 'allowed': {'admin'}, 'label': 'Payment Logs' },
            { 'keys': {'payment'},
              'url': '/admin_payment/', 'allowed': {'admin'}, 'label': 'Record Payment' },
            { 'keys': {'payment history'},
              'url': '/admin_fees/', 'allowed': {'admin'}, 'label': 'Payment History' },
            { 'keys': {'mpesa reconcile'},
              'url': '/admin/fees/mpesa/reconcile/', 'allowed': {'admin'}, 'label': 'M-Pesa Reconcile' },
            { 'keys': {'attendance view'},
              'url': '/attendance/view/', 'allowed': {'admin'}, 'label': 'Attendance View' },
            { 'keys': {'events'},
              'url': '/admin_events/', 'allowed': {'admin'}, 'label': 'Admin Events' },
            { 'keys': {'analytics','reports','insights','stats'},
              'url': '/admin_analytics/', 'allowed': {'admin'}, 'label': 'Admin Analytics' },
            { 'keys': {'users','accounts','staff'},
              'url': '/admin_users/', 'allowed': {'admin'}, 'label': 'Manage Users' },
            { 'keys': {'messages','messaging','chat','inbox'},
              'url': '/teacher_messaging/' if role == 'teacher' else ('/admin_messaging/' if role == 'admin' else ('/clerk_messaging/' if role == 'clerk' else None)),
              'allowed': {'admin','teacher','clerk'}, 'label': 'Messaging' },
            { 'keys': {'dashboard','home','start','main'},
              'url': '/dashboard/', 'allowed': {'admin','teacher','clerk','student','parent',''}, 'label': 'Dashboard' },
            { 'keys': {'fees','payments','finance'},
              'url': '/admin_fees/', 'allowed': {'admin'}, 'label': 'Admin Fees' },
            { 'keys': {'timetable','schedule','calendar'},
              'url': (f'/teacher/{tid}/timetable/' if role == 'teacher' and tid else '/timetable/'),
              'allowed': {'admin','teacher'}, 'label': 'Timetable' },
            { 'keys': {'attendance','rollcall','roll-call'},
              'url': (f'/teacher/{tid}/attendance/' if role == 'teacher' and tid else None),
              'allowed': {'teacher'}, 'label': 'Attendance' },
            { 'keys': {'grades','upload grades','marks','bulk grades','excel grades'},
              'url': (f'/teacher/{tid}/upload-grades/' if role == 'teacher' and tid else None),
              'allowed': {'teacher'}, 'label': 'Upload Grades' },
            { 'keys': {'manage grades','markbook'},
              'url': (f'/teacher/{tid}/grades/' if role == 'teacher' and tid else None),
              'allowed': {'teacher'}, 'label': 'Manage Grades' },
            { 'keys': {'gradebook'},
              'url': (f'/teacher/{tid}/gradebook/' if role == 'teacher' and tid else None),
              'allowed': {'teacher'}, 'label': 'Gradebook' },
            { 'keys': {'profile','account'},
              'url': (f'/teacher/{tid}/profile/' if role == 'teacher' and tid else None),
              'allowed': {'teacher'}, 'label': 'Teacher Profile' },
            { 'keys': {'classes','responsibilities'},
              'url': (f'/teacher_dashboard/{tid}/' if role == 'teacher' and tid else None),
              'allowed': {'teacher'}, 'label': 'Your Classes & Responsibilities' },
            { 'keys': {'exams','tests'},
              'url': '/admin_exams/', 'allowed': {'admin'}, 'label': 'Admin Exams' },
        ]
        matched = None
        # Exact/contains match first
        for c in candidates:
            if any(k in target for k in c['keys']):
                matched = c
                break
        # Fuzzy match if still not matched
        if not matched:
            # Build a flat list of all keys to match
            all_keys = []
            key_to_candidate = {}
            for c in candidates:
                for k in c['keys']:
                    all_keys.append(k)
                    key_to_candidate[k] = c
            fk = _fuzzy_find_in_text(target, all_keys)
            if fk:
                matched = key_to_candidate.get(fk)
        if not matched:
            return False, "Sorry, I couldn't recognize that page. Try: analytics, users, messages, dashboard.", None, [
                {"text": "open analytics"},
                {"text": "open users"},
                {"text": "open messages"},
            ]
        if role not in matched['allowed']:
            return False, "You're not authorized to access that page.", None, [
                {"text": "open dashboard"},
                {"text": "open messages"},
            ]
        if not matched['url']:
            # Provide a clearer error if teacher mapping is missing
            if role == 'teacher' and any(k in target for k in {'timetable','attendance','grades','gradebook','profile','classes','responsibilities'}):
                return False, "Your teacher profile couldn't be found. Please contact admin.", None, [{"text": "open dashboard"}]
            return False, "Messaging is not available for your role.", None, [{"text": "open dashboard"}]
        action = {"type": "navigate", "url": matched['url']}
        fmt = slots.get('respond_format') or request.session.get('assistant_format')
        msg = _format_message(f"Opening: {matched['label']}", fmt)
        return True, msg, action, []

    if intent == 'export_shortcut':
        if role != 'admin':
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return False, _format_message("Exports are available for admins only.", fmt), None, []
        q = (slots.get('query') or '').lower()
        # Determine resource and format
        resources = {
            'users': {'csv': '/exports/users.csv', 'pdf': '/exports/users.pdf'},
            'teachers': {'csv': '/exports/teachers.csv', 'pdf': '/exports/teachers.pdf'},
            'students': {'csv': '/exports/students.csv', 'pdf': '/exports/students.pdf'},
            'fee-assignments': {'csv': '/exports/fee-assignments.csv', 'pdf': '/exports/fee-assignments.pdf'},
            'fee payments': {'csv': '/exports/fee-payments.csv', 'pdf': '/exports/fee-payments.pdf'},
            'students with arrears': {'csv': '/exports/students-with-arrears.csv', 'pdf': '/exports/students-with-arrears.pdf'},
            'students without arrears': {'csv': '/exports/students-without-arrears.csv', 'pdf': '/exports/students-without-arrears.pdf'},
            'result slip': {'csv': '/exports/result-slip.csv', 'pdf': '/exports/result-slip.pdf'},
        }
        fmts = ['pdf', 'csv']
        res_key = _fuzzy_find_in_text(q, list(resources.keys()))
        fmt = _fuzzy_find_in_text(q, fmts) or 'pdf'
        if res_key and fmt in fmts:
            url = resources[res_key].get(fmt)
            if url:
                fmt_pref = slots.get('respond_format') or request.session.get('assistant_format')
                return True, _format_message(f"Downloading {res_key.title()} ({fmt.upper()}).", fmt_pref), {"type": "navigate", "url": url}, []
        # Some exports require parameters; fallback to downloads hub
        fmt_pref = slots.get('respond_format') or request.session.get('assistant_format')
        return True, _format_message("Opening Downloads. Some exports need extra filters.", fmt_pref), {"type": "navigate", "url": "/downloads/"}, [
            {"text": "exports"}
        ]

    if intent == 'open_class_profile':
        if role != 'admin':
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return False, _format_message("Only admins can open Class Profile from here.", fmt), None, []
        cls_text = slots.get('class_text')
        cls, name_match = _resolve_class_by_text(cls_text)
        if not cls:
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return False, _format_message("Couldn't find that class.", fmt), None, [{"text": "open classes"}]
        url = f"/class_profile/{cls.id}/"
        fmt = slots.get('respond_format') or request.session.get('assistant_format')
        return True, _format_message(f"Opening Class Profile: {name_match}.", fmt), {"type": "navigate", "url": url}, []

    if intent == 'open_class_result_slip':
        cls_text = slots.get('class_text')
        cls, name_match = _resolve_class_by_text(cls_text)
        if not cls:
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return False, _format_message("Couldn't find that class.", fmt), None, [{"text": "classes"}]
        if role == 'admin':
            url = f"/admin_class_result_slip/{cls.id}/"
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return True, _format_message(f"Opening Result Slip for {name_match}.", fmt), {"type": "navigate", "url": url}, []
        if role == 'teacher':
            url = f"/teacher_class_result_slip/{cls.id}/"
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return True, _format_message(f"Opening Result Slip for {name_match}.", fmt), {"type": "navigate", "url": url}, []
        fmt = slots.get('respond_format') or request.session.get('assistant_format')
        return False, _format_message("This action is available to admins and teachers only.", fmt), None, []

    if intent == 'teacher_attendance_for':
        if role != 'teacher':
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return False, _format_message("Only teachers can take attendance.", fmt), None, []
        tail = (slots.get('tail') or '')
        cls, cname = _resolve_class_by_text(tail)
        sub, sname = _resolve_subject_by_text(tail)
        try:
            from core.models import Teacher
            t = Teacher.objects.filter(user=user).only('id').first()
            if not t:
                return False, "Your teacher profile couldn't be found.", None, []
            if cls and sub:
                url = f"/teacher/{t.id}/attendance/{cls.id}/{sub.id}/"
                fmt = slots.get('respond_format') or request.session.get('assistant_format')
                return True, _format_message(f"Taking attendance: {cname} - {sname}.", fmt), {"type": "navigate", "url": url}, []
            # Fallback to attendance home
            url = f"/teacher/{t.id}/attendance/"
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return True, _format_message("Opening Attendance. Select class and subject.", fmt), {"type": "navigate", "url": url}, []
        except Exception:
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return False, _format_message("Couldn't open attendance.", fmt), None, []

    if intent == 'teacher_input_grades_for':
        if role != 'teacher':
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return False, _format_message("Only teachers can input grades.", fmt), None, []
        tail = (slots.get('tail') or '')
        cls, cname = _resolve_class_by_text(tail)
        sub, sname = _resolve_subject_by_text(tail)
        exm, ename = _resolve_exam_by_text(tail)
        try:
            from core.models import Teacher
            t = Teacher.objects.filter(user=user).only('id').first()
            if not t:
                return False, "Your teacher profile couldn't be found.", None, []
            if cls and sub and exm:
                url = f"/teacher/{t.id}/grades/{cls.id}/{sub.id}/{exm.id}/"
                fmt = slots.get('respond_format') or request.session.get('assistant_format')
                return True, _format_message(f"Opening grade entry for {cname}, {sname}, {ename}.", fmt), {"type": "navigate", "url": url}, []
            # Partial info -> send to manage grades
            url = f"/teacher/{t.id}/grades/"
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return True, _format_message("Opening Manage Grades. Choose class/subject/exam.", fmt), {"type": "navigate", "url": url}, []
        except Exception:
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return False, _format_message("Couldn't open grade entry.", fmt), None, []

    if intent == 'teacher_exam_results_for':
        if role != 'teacher':
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return False, _format_message("Only teachers can view class exam results here.", fmt), None, []
        tail = (slots.get('tail') or '')
        cls, cname = _resolve_class_by_text(tail)
        sub, sname = _resolve_subject_by_text(tail)
        exm, ename = _resolve_exam_by_text(tail)
        try:
            from core.models import Teacher
            t = Teacher.objects.filter(user=user).only('id').first()
            if not t:
                return False, "Your teacher profile couldn't be found.", None, []
            if cls and sub and exm:
                url = f"/teacher/{t.id}/results/{cls.id}/{sub.id}/{exm.id}/"
                fmt = slots.get('respond_format') or request.session.get('assistant_format')
                return True, _format_message(f"Opening exam results for {cname}, {sname}, {ename}.", fmt), {"type": "navigate", "url": url}, []
            # If class only, take them to teacher class result slip
            if cls and (not sub or not exm):
                url = f"/teacher_class_result_slip/{cls.id}/"
                fmt = slots.get('respond_format') or request.session.get('assistant_format')
                return True, _format_message(f"Opening class result slip for {cname}.", fmt), {"type": "navigate", "url": url}, []
            # Fallback to gradebook
            url = f"/teacher/{t.id}/gradebook/"
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return True, _format_message("Opening Gradebook.", fmt), {"type": "navigate", "url": url}, []
        except Exception:
            fmt = slots.get('respond_format') or request.session.get('assistant_format')
            return False, _format_message("Couldn't open exam results.", fmt), None, []

    if intent == 'set_response_format':
        fmt = (slots.get('format') or 'plain')
        if fmt not in {'plain','bullets','json','table'}:
            return False, "Unsupported format. Use plain, bullets, json, or table.", None, []
        # Persist per-user in Django session
        try:
            request.session['assistant_format'] = fmt
        except Exception:
            pass
        return True, _format_message(f"Okay. I'll use {fmt} format.", fmt), None, []

    if intent == 'teacher_result_slip':
        if role != 'teacher':
            return False, "This action is only for teachers.", None, []
        # Navigate teacher to their dashboard where class cards exist (use Teacher.id)
        try:
            from core.models import Teacher
            t = Teacher.objects.filter(user=user).only('id').first()
            if not t:
                return False, "Your teacher profile couldn't be found.", None, [{"text": "open dashboard"}]
            action = {"type": "navigate", "url": f"/teacher_dashboard/{t.id}/"}
        except Exception:
            return False, "Couldn't navigate to your dashboard.", None, [{"text": "open dashboard"}]
        return True, "Taking you to your dashboard. Use the Result Slip buttons on your class cards.", action, [
            {"text": "open dashboard"}
        ]

    if intent == 'student_results':
        if role != 'student':
            return False, "This action is only for students.", None, []
        # Navigate to the logged-in student's profile Performance tab
        try:
            from core.models import Student
            stu = Student.objects.filter(user=user).first()
            if not stu:
                return False, "Your student profile was not found.", None, []
            # Enforce fee-based restriction before navigation
            try:
                from core.views import can_view_results_for_student
                can_view, msg, restrict_flag = can_view_results_for_student(request, stu)
            except Exception:
                can_view, msg, restrict_flag = True, "", False
            if not can_view and restrict_flag:
                blk_url = f"/results/blocked/?msg={quote(msg or 'Results are temporarily unavailable due to outstanding fees.') }"
                action = {"type": "navigate", "url": blk_url}
                return True, "Your results are currently restricted.", action, []
            url = f"/student_profile/{stu.id}/?tab=performance"
            action = {"type": "navigate", "url": url}
            return True, "Opening your results (Performance).", action, []
        except Exception:
            return False, "Couldn't locate your results right now.", None, [{"text": "open dashboard"}]

    if intent == 'admin_record_payment':
        if role != 'admin':
            return False, "This action is only for admins.", None, []
        action = {"type": "navigate", "url": "/admin_fees/"}
        return True, "Opening Admin Fees so you can record a payment.", action, [
            {"text": "open analytics"},
            {"text": "open users"},
        ]

    # Fallback
    return False, "I didn't get that. Type ‘help’ for what I can do.", None, [
        {"text": "help"},
        {"text": "open analytics"},
    ]


@login_required(login_url='login')
@require_http_methods(["GET"])
# Simple JSON history for the active session
def history(request):
    session = _ensure_session(request.user)
    items = [
        {
            'role': m.role,
            'text': m.text,
            'created_at': timezone.localtime(m.created_at).isoformat(),
        }
        for m in session.messages.order_by('created_at')[:50]
    ]
    return JsonResponse({'messages': items})


@login_required(login_url='login')
@require_http_methods(["POST"])
# Clears current bot session message history
def clear_history(request):
    session = _ensure_session(request.user)
    # Delete messages for this active session
    try:
        deleted = session.messages.all().delete()
        BotActionLog.objects.create(
            user=request.user,
            intent='clear_history',
            slots={},
            success=True,
            message='History cleared',
        )
        return JsonResponse({'ok': True, 'cleared': True})
    except Exception:
        return JsonResponse({'ok': False, 'cleared': False}, status=500)

# Accepts {text: "..."}
def message(request):
    text = (request.POST.get('text') or '').strip()
    if not text:
        return HttpResponseBadRequest('Missing text')

    session = _ensure_session(request.user)
    BotMessage.objects.create(session=session, role='user', text=text)

    intent, slots = _intent_router(text, request.user)
    ok, reply, action, suggestions = _handle_intent(intent, slots, request)

    BotActionLog.objects.create(
        user=request.user,
        intent=intent,
        slots=slots,
        success=ok,
        message=reply,
    )
    BotMessage.objects.create(session=session, role='bot', text=reply)

    return JsonResponse({'ok': ok, 'reply': reply, 'action': action, 'suggestions': suggestions})

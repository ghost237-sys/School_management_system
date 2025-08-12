from django.shortcuts import render

def landing_page(request):
    context = {
        'school_name': 'Greenwood High',
        'school_aim': 'To nurture and inspire every student to reach their full potential.',
        'school_motto': 'Excellence Through Diligence'
    }
    return render(request, 'landing/index.html', context)


# Create your views here.

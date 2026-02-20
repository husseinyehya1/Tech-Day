from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Workshop


@login_required
def workshop_list(request):
    workshops = Workshop.objects.select_related('supervisor').all()
    return render(request, 'workshops/list.html', {'workshops': workshops})

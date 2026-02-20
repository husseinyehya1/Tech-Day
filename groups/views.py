from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Group


@login_required
def group_list(request):
    groups = Group.objects.all()
    return render(request, 'groups/list.html', {'groups': groups})

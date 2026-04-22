from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Group


from dashboard.models import Event

@login_required
def group_list(request):
    current_event = Event.get_current()
    groups = Group.objects.filter(event=current_event)
    return render(request, 'groups/list.html', {'groups': groups})

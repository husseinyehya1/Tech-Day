from django.template import engines
django_engine = engines['django']
if 'workshop_tags' in django_engine.engine.libraries:
    print("Library 'workshop_tags' is registered.")
else:
    print("Library 'workshop_tags' is NOT registered.")
    print("Available libraries:", list(django_engine.engine.libraries.keys()))

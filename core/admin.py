# core/admin.py
from django.contrib import admin
from .models import Document, Summary, FactCheck

admin.site.register(Document)
admin.site.register(Summary)
admin.site.register(FactCheck)
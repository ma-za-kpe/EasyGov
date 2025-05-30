# core/admin.py
from django.contrib import admin
from .models import Document, Summary, FactCheck
from django import forms

class DocumentAdminForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        pdf_file = cleaned_data.get('pdf_file')
        pdf_url = cleaned_data.get('pdf_url')
        if not pdf_file and not pdf_url:
            raise forms.ValidationError("You must provide either a PDF file or a PDF URL.")
        return cleaned_data

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    form = DocumentAdminForm
    list_display = ('title', 'region', 'uploaded_at', 'summarization_processed', 'should_summarize')
    list_filter = ('region', 'summarization_processed', 'should_summarize')
    search_fields = ('title',)
    fields = ('title', 'pdf_file', 'pdf_url', 'source_url', 'is_verified', 'region', 'should_summarize')

@admin.register(Summary)
class SummaryAdmin(admin.ModelAdmin):
    list_display = ('document', 'language', 'created_at')
    list_filter = ('language',)
    search_fields = ('document__title', 'text')

@admin.register(FactCheck)
class FactCheckAdmin(admin.ModelAdmin):
    list_display = ('summary', 'is_verified', 'checked_at')
    list_filter = ('is_verified',)






# # core/admin.py
# from django.contrib import admin
# from django.contrib.admin.actions import delete_selected
# from django.contrib import messages
# from .models import Document, Summary, FactCheck

# class SummaryInline(admin.TabularInline):
#     model = Summary
#     extra = 0
#     readonly_fields = ['language', 'created_at']
#     fields = ['language', 'text', 'created_at']
#     can_delete = False
    
#     def has_add_permission(self, request, obj=None):
#         return False  # Summaries are created automatically

# class FactCheckInline(admin.TabularInline):
#     model = FactCheck
#     extra = 0
#     fields = ['source_url', 'is_verified', 'checked_at']
#     readonly_fields = ['checked_at']

# @admin.register(Document)
# class DocumentAdmin(admin.ModelAdmin):
#     list_display = ['title', 'region', 'is_verified', 'summarization_processed']
#     list_filter = ['region', 'is_verified', 'summarization_processed']
#     search_fields = ['title']
#     readonly_fields = ['uploaded_at', 'summarization_processed']
#     list_editable = ['is_verified']
#     inlines = [SummaryInline]
#     fieldsets = (
#         (None, {
#             'fields': ('title', 'pdf_url', 'region')
#         }),
#         ('Verification', {
#             'fields': ('source_url', 'is_verified')
#         }),
#         ('Processing Status', {
#             'fields': ('uploaded_at', 'summarization_processed', 'should_summarize'),
#             'classes': ('collapse',)
#         })
#     )
    
#     # Include default delete action and custom actions
#     actions = [delete_selected, 'mark_as_verified', 'mark_as_unverified', 'trigger_summarization']

#     def save_model(self, request, obj, form, change):
#         """Override save_model to handle summarization queuing"""
#         # For new documents, we can let it be processed normally
#         # Celery will handle the processing in the background
#         super().save_model(request, obj, form, change)
        
#         # Show a helpful message
#         if not change:  # New document
#             messages.info(request, "Document saved. Summarization will be processed in the background.")

#     def mark_as_verified(self, request, queryset):
#         """Mark documents as verified"""
#         updated = queryset.update(is_verified=True)
#         for doc in queryset:
#             for summary in doc.summaries.all():
#                 FactCheck.objects.filter(summary=summary).update(is_verified=True)
#         self.message_user(request, f"{updated} documents marked as verified.")
#     mark_as_verified.short_description = "Mark selected documents as verified"

#     def mark_as_unverified(self, request, queryset):
#         """Mark documents as unverified"""
#         updated = queryset.update(is_verified=False)
#         for doc in queryset:
#             for summary in doc.summaries.all():
#                 FactCheck.objects.filter(summary=summary).update(is_verified=False)
#         self.message_user(request, f"{updated} documents marked as unverified.")
#     mark_as_unverified.short_description = "Mark selected documents as unverified"
    
#     def trigger_summarization(self, request, queryset):
#         """Manually trigger summarization for selected documents"""
#         # Import Celery task
#         from .tasks import process_document_summaries
        
#         count = 0
#         for doc in queryset:
#             # Queue the task for processing
#             process_document_summaries.delay(doc.id)
#             count += 1
            
#         self.message_user(request, f"{count} documents queued for re-summarization. Processing will happen in the background.")
#     trigger_summarization.short_description = "Re-generate summaries for selected documents"

# @admin.register(Summary)
# class SummaryAdmin(admin.ModelAdmin):
#     list_display = ['id', 'document_title', 'language', 'created_at', 'has_fact_check', 'is_verified']
#     list_filter = ['language', 'created_at']
#     search_fields = ['document__title', 'text']
#     readonly_fields = ['document', 'language', 'created_at', 'text']
#     inlines = [FactCheckInline]
    
#     def document_title(self, obj):
#         return obj.document.title
#     document_title.short_description = 'Document'
    
#     def has_fact_check(self, obj):
#         return FactCheck.objects.filter(summary=obj).exists()
#     has_fact_check.boolean = True
#     has_fact_check.short_description = 'Fact Check'
    
#     def is_verified(self, obj):
#         fact_check = FactCheck.objects.filter(summary=obj).first()
#         return fact_check.is_verified if fact_check else False
#     is_verified.boolean = True
#     is_verified.short_description = 'Verified'
    
#     def has_add_permission(self, request):
#         return False  # Summaries are created automatically

# @admin.register(FactCheck)
# class FactCheckAdmin(admin.ModelAdmin):
#     list_display = ['id', 'summary_title', 'is_verified', 'checked_at']
#     list_filter = ['is_verified', 'checked_at']
#     list_editable = ['is_verified']
#     search_fields = ['summary__document__title', 'source_url']
#     readonly_fields = ['checked_at']
    
#     def summary_title(self, obj):
#         return f"{obj.summary.document.title} ({obj.summary.language})"
#     summary_title.short_description = 'Summary'
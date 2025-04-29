# core/admin.py
from django.contrib import admin
from .models import Document, Summary, FactCheck

class SummaryInline(admin.TabularInline):
    model = Summary
    extra = 0
    readonly_fields = ['language', 'created_at']
    fields = ['language', 'text', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False  # Summaries are created automatically

class FactCheckInline(admin.TabularInline):
    model = FactCheck
    extra = 0
    fields = ['source_url', 'is_verified', 'checked_at']
    readonly_fields = ['checked_at']

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'region', 'uploaded_at', 'source_url', 'is_verified', 'summarization_processed']
    list_filter = ['region', 'is_verified', 'summarization_processed']
    search_fields = ['title']
    readonly_fields = ['uploaded_at', 'summarization_processed']
    list_editable = ['is_verified']
    inlines = [SummaryInline]
    fieldsets = (
        (None, {
            'fields': ('title', 'pdf_url', 'region')
        }),
        ('Verification', {
            'fields': ('source_url', 'is_verified')
        }),
        ('Processing Status', {
            'fields': ('uploaded_at', 'summarization_processed'),
            'classes': ('collapse',)
        })
    )
    actions = ['mark_as_verified', 'mark_as_unverified', 'trigger_resummary']

    def mark_as_verified(self, request, queryset):
        updated = queryset.update(is_verified=True)
        # Also update all related fact checks
        for doc in queryset:
            for summary in doc.summaries.all():
                FactCheck.objects.filter(summary=summary).update(is_verified=True)
        self.message_user(request, f"{updated} documents marked as verified.")
    mark_as_verified.short_description = "Mark selected documents as verified"

    def mark_as_unverified(self, request, queryset):
        updated = queryset.update(is_verified=False)
        # Also update all related fact checks
        for doc in queryset:
            for summary in doc.summaries.all():
                FactCheck.objects.filter(summary=summary).update(is_verified=False)
        self.message_user(request, f"{updated} documents marked as unverified.")
    mark_as_unverified.short_description = "Mark selected documents as unverified"
    
    def trigger_resummary(self, request, queryset):
        for doc in queryset:
            # Set flag to false to trigger re-summarization on save
            doc.summarization_processed = False
            doc.save()
        self.message_user(request, f"{queryset.count()} documents queued for re-summarization.")
    trigger_resummary.short_description = "Re-generate summaries for selected documents"

@admin.register(Summary)
class SummaryAdmin(admin.ModelAdmin):
    list_display = ['id', 'document_title', 'language', 'created_at', 'has_fact_check', 'is_verified']
    list_filter = ['language', 'created_at']
    search_fields = ['document__title', 'text']
    readonly_fields = ['document', 'language', 'created_at', 'text']
    inlines = [FactCheckInline]
    
    def document_title(self, obj):
        return obj.document.title
    document_title.short_description = 'Document'
    
    def has_fact_check(self, obj):
        return FactCheck.objects.filter(summary=obj).exists()
    has_fact_check.boolean = True
    has_fact_check.short_description = 'Fact Check'
    
    def is_verified(self, obj):
        fact_check = FactCheck.objects.filter(summary=obj).first()
        return fact_check.is_verified if fact_check else False
    is_verified.boolean = True
    is_verified.short_description = 'Verified'
    
    def has_add_permission(self, request):
        return False  # Summaries are created automatically

@admin.register(FactCheck)
class FactCheckAdmin(admin.ModelAdmin):
    list_display = ['id', 'summary_title', 'is_verified', 'checked_at']
    list_filter = ['is_verified', 'checked_at']
    list_editable = ['is_verified']
    search_fields = ['summary__document__title', 'source_url']
    readonly_fields = ['checked_at']
    
    def summary_title(self, obj):
        return f"{obj.summary.document.title} ({obj.summary.language})"
    summary_title.short_description = 'Summary'
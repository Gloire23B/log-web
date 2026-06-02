"""apps/services/forms.py — Formulaire de gestion des services."""
from django import forms
from .models import Service

INPUT_CLS = (
    "w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-4 py-2.5 "
    "text-[#E6EDF3] placeholder-[#484F58] text-sm "
    "focus:outline-none focus:border-[#388BFD] focus:ring-1 focus:ring-[#388BFD] "
    "transition-colors duration-200"
)
CHECKBOX_CLS = (
    "w-4 h-4 rounded border-[#30363D] bg-[#0D1117] text-[#388BFD] "
    "focus:ring-[#388BFD] focus:ring-offset-0"
)


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            "name", "display_name", "description", "service_type", "status",
            "version", "endpoint", "avg_latency_ms", "p95_latency_ms",
            "error_rate", "requests_per_sec", "uptime_30d", "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2, "class": INPUT_CLS + " resize-none"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = CHECKBOX_CLS
            elif not isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("class", INPUT_CLS)
        for fname in ["display_name", "description", "version", "endpoint",
                      "avg_latency_ms", "p95_latency_ms", "error_rate",
                      "requests_per_sec", "uptime_30d"]:
            self.fields[fname].required = False

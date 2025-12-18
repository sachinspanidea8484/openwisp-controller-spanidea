
from django import forms
from django.forms import inlineformset_factory
from .models import ExecutionArtifact, TestSuiteExecution

class ExecutionArtifactForm(forms.ModelForm):
    class Meta:
        model = ExecutionArtifact
        fields = ("config_file",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ override model requirement
        self.fields["config_file"].required = False
ExecutionArtifactFormSet = inlineformset_factory(
    TestSuiteExecution,
    ExecutionArtifact,
    form=ExecutionArtifactForm,
    extra=0,
    can_delete=False,
)
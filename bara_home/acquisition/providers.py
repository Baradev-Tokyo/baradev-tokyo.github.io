"""Optional on-device assessment using an existing GGUF and a trusted llama.cpp CLI."""

import json
from pathlib import Path
import shutil
import subprocess

from .screening import RulesProvider


class UnavailableProvider(RuntimeError):
    pass


class LlamaCppProvider:
    def __init__(self, model, rules=None):
        self.model = Path(model).resolve()
        if self.model.suffix.lower() != ".gguf" or not self.model.is_file():
            raise ValueError("Choose an existing local GGUF file.")
        self.rules = rules or RulesProvider()

    def assess(self, opportunity):
        baseline = self.rules.assess(opportunity)
        executable = shutil.which("llama-cli")
        if not executable:
            return {**baseline, "local_model_status": "unavailable"}

        # Only these structured categories enter the model. Its output cannot gate a proposal.
        prompt = "Summarize these review risks without inventing facts: " + json.dumps(
            {"missing": baseline["missing_information"], "risks": baseline["risks"]}
        )
        try:
            result = subprocess.run(
                [executable, "-m", str(self.model), "-p", prompt, "-n", "128",
                 "-c", "1024", "-t", "2", "-ngl", "0", "--no-display-prompt", "--no-conversation"],
                check=True, timeout=45, capture_output=True, encoding="utf-8", errors="replace",
            )
        except (OSError, subprocess.SubprocessError):
            return {**baseline, "local_model_status": "unavailable"}
        return {**baseline, "local_model_status": "advisory", "local_model_notes": result.stdout.strip()[:2000]}


class OpenAIProvider:
    def assess(self, opportunity):
        raise UnavailableProvider("OpenAI API use is disabled by the zero-cost policy.")

"""
dataset.py

Defines MedPixDataset for loading and sampling MedPix report records with modality tagging.
"""
import os
from utils import load_json, stratified_sample

class MedPixDataset:
    """
    Dataset wrapper for MedPix reports. Loads raw records, infers or validates modality,
    and provides stratified batch sampling.
    """
    def __init__(self, data_path: str, prompts_path: str = None):
        # Load raw MedPix records
        self.records = load_json(data_path)
        # Optionally load modality definitions from prompts file
        self.modalities = []
        if prompts_path and os.path.exists(prompts_path):
            prompts = load_json(prompts_path)
            # top-level keys are modality names
            self.modalities = list(prompts.keys())
        # Ensure each record has a modality field
        for rec in self.records:
            if 'modality' not in rec or not rec['modality']:
                rec['modality'] = self._infer_modality(rec)

    def _infer_modality(self, record: dict) -> str:
        """
        Infer modality from record content (e.g., question text) by matching known modality keywords.
        Falls back to 'unknown' if no match.
        """
        text = record.get('question', '') or record.get('report_text', '') or ''
        text_lower = text.lower()
        for mod in self.modalities:
            if mod.lower() in text_lower:
                return mod
        # fallback to any pre-existing modality or unknown
        return record.get('modality', 'unknown')

    def get_stratified_batch(self, start: int, size: int) -> list:
        """
        Skip first `start` records, then return a stratified sample of `size` records
        balanced across modalities.
        """
        pending = self.records[start:]
        if not pending:
            return []
        # sample evenly across 'modality'
        batch = stratified_sample(pending, size, key='modality')
        return batch

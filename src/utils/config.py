import yaml


def load_config(path="src/config/modalities.yaml"):
    """
    Load modalities configuration from YAML file.
    Returns a dict mapping modality names to their config.
    """
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    return cfg.get('modalities', {})

from pathlib import Path
from mitreattack.stix20 import MitreAttackData

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_FILE = PROJECT_ROOT / "enterprise-attack.json"

def main():
    mitre_attack_data = MitreAttackData(str(DATA_FILE))


    techniques = mitre_attack_data.get_techniques(remove_revoked_deprecated=True)

    for tech in techniques[:10]:
        print(tech)

if __name__ == "__main__":
    main()

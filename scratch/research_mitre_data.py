from pathlib import Path
from mitreattack.stix20 import MitreAttackData
import json

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_FILE = PROJECT_ROOT / "enterprise-attack.json"

def main():
    if not DATA_FILE.exists():
        print(f"Data file not found at {DATA_FILE}")
        return

    print(f"Loading MITRE data from {DATA_FILE}...")
    mitre_attack_data = MitreAttackData(str(DATA_FILE))

    # Explore Groups
    groups = mitre_attack_data.get_groups()
    print(f"Found {len(groups)} groups.")
    
    if groups:
        sample_group = groups[0]
        print("\n--- Sample Group ---")
        # print(json.dumps(sample_group, indent=2)) # This might be too long
        print(f"Name: {sample_group.get('name')}")
        print(f"ID: {sample_group.get('external_references')[0].get('external_id') if sample_group.get('external_references') else 'N/A'}")
        
        # Get techniques used by this group
        group_stix_id = sample_group['id']
        print(f"Group STIX ID: {group_stix_id}")
        print(f"Group Type: {type(sample_group)}")
        
        # Try passing the group object directly (as the docs suggest) or the ID
        try:
            techniques_used = mitre_attack_data.get_techniques_used_by_group(sample_group)
            print(f"Techniques used (via object): {len(techniques_used)}")
        except Exception as e:
            print(f"Error using object: {e}")
            
        try:
            # Maybe it needs the ID string?
            # Actually let's just use the helper to get all relationships and filter
            pass
        except Exception as e:
            print(f"Error using ID: {e}")

    # Explore Techniques
    techniques = mitre_attack_data.get_techniques()
    print(f"\nFound {len(techniques)} techniques.")
    if techniques:
        sample_tech = techniques[0]
        print("\n--- Sample Technique ---")
        print(f"Name: {sample_tech.get('name')}")
        print(f"ID: {sample_tech.get('external_references')[0].get('external_id') if sample_tech.get('external_references') else 'N/A'}")

    # Explore Software
    software = mitre_attack_data.get_software()
    print(f"\nFound {len(software)} software.")

if __name__ == "__main__":
    main()

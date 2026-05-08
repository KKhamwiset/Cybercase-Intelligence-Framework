import os
import requests
from pathlib import Path
from datetime import datetime
# pyrefly: ignore [missing-import]
from mitreattack.stix20 import MitreAttackData
from fpdf import FPDF

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_FILE = PROJECT_ROOT / "enterprise-attack.json"
DATA_URL = "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json"
OUTPUT_PDF = PROJECT_ROOT / "Documents/mitre_attack_report.pdf"

# Font path from mitreattack package
FONT_SANS = PROJECT_ROOT / "env_mitre/Lib/site-packages/mitreattack/navlayers/exporters/fonts/sans-serif.ttf"

class MITREPDFExporter(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, "MITRE ATT&CK Intelligence Report", 0, 0, "R")
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")

    def create_cover_page(self):
        self.add_page()
        self.set_fill_color(0, 91, 148)  # MITRE Blue
        self.rect(0, 0, 210, 297, 'F')
        
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 32)
        self.set_y(100)
        self.multi_cell(0, 15, "MITRE ATT&CK\nIntelligence Report", 0, "C")
        
        self.set_font("Helvetica", "", 16)
        self.set_y(150)
        self.cell(0, 10, f"Generated on: {datetime.now().strftime('%B %d, %Y')}", 0, 1, "C")
        
        self.set_y(250)
        self.set_font("Helvetica", "I", 10)
        self.cell(0, 10, "A comprehensive guide to Threat Groups and Techniques", 0, 1, "C")

    def add_group_section(self, group, techniques):
        self.add_page()
        
        # Group Header
        self.set_fill_color(240, 240, 240)
        self.set_text_color(0, 91, 148)
        self.set_font("Helvetica", "B", 18)
        
        name = group.get("name", "Unknown Group")
        external_refs = group.get("external_references", [])
        group_id = external_refs[0].get("external_id", "N/A") if external_refs else "N/A"
        
        self.cell(0, 15, f"{name} ({group_id})", 0, 1, "L", fill=True)
        self.ln(5)
        
        # Description
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "Description", 0, 1, "L")
        
        self.set_font("Helvetica", "", 10)
        description = group.get("description", "No description available.")
        # Clean up text for FPDF (handle basic encoding issues)
        description = description.encode('latin-1', 'replace').decode('latin-1')
        self.multi_cell(0, 5, description)
        self.ln(10)
        
        # Techniques Table
        if techniques:
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(0, 91, 148)
            self.cell(0, 10, "Techniques Used", 0, 1, "L")
            
            # Table Header
            self.set_fill_color(0, 91, 148)
            self.set_text_color(255, 255, 255)
            self.set_font("Helvetica", "B", 10)
            self.cell(40, 8, "ID", 1, 0, "C", fill=True)
            self.cell(0, 8, "Name", 1, 1, "C", fill=True)
            
            # Table Rows
            self.set_text_color(0, 0, 0)
            self.set_font("Helvetica", "", 9)
            sorted_techs = sorted(techniques, key=lambda x: x.get("external_references", [{}]))
            
            for tech in sorted_techs:
                t_refs = tech.get("external_references", [])
                t_sname = t_refs[0].get("source_name", "N/A") if t_refs else "N/A"
                t_id = t_refs[0].get("external_id", "N/A") if t_refs else "N/A"
                

                if self.get_y() > 270:
                    self.add_page()
                    # Repeat header
                    self.set_fill_color(0, 91, 148)
                    self.set_text_color(255, 255, 255)
                    self.set_font("Helvetica", "B", 10)
                    self.cell(40, 8, "ID", 1, 0, "C", fill=True)
                    self.cell(0, 8, "Name", 1, 1, "C", fill=True)
                    self.set_text_color(0, 0, 0)
                    self.set_font("Helvetica", "", 9)

                self.cell(40, 7, t_id, 1, 0, "C")
                self.cell(0, 7, t_name, 1, 1, "L")

def download_data(url, output_path):
    """Download the MITRE ATT&CK STIX data."""
    print(f"[*] Downloading MITRE data from {url}...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"[+] Download complete: {output_path}")
    except Exception as e:
        print(f"[-] Error downloading data: {e}")
        raise

def main():
    if not DATA_FILE.exists():
        print(f"[!] Data file not found at {DATA_FILE}")
        download_data(DATA_URL, DATA_FILE)

    print(f"[*] Loading MITRE data from {DATA_FILE} (this may take a moment)...")
    mitre_attack_data = MitreAttackData(str(DATA_FILE))

    print("[*] Retrieving groups...")
    groups = mitre_attack_data.get_groups()
    print(f"[+] Successfully retrieved {len(groups)} groups.")

    # Sort groups by name
    groups = sorted(groups, key=lambda x: x.get("name", "").lower())

    print(f"[*] Initializing PDF Report: {OUTPUT_PDF}")
    pdf = MITREPDFExporter()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Try to add custom font if it exists
    if FONT_SANS.exists():
        try:
            # fpdf2 uses add_font slightly differently depending on version
            # But let's stick to core Helvetica for maximum compatibility unless we really need custom
            # For now, I'll skip add_font to avoid potential issues with TTF parsing in this env
            pass
        except Exception as e:
            print(f"[!] Warning: Could not load custom font: {e}")

    pdf.create_cover_page()

    print("[*] Generating content for groups...")
    total = len(groups)
    
    for i, group in enumerate(groups):
        g_name = group.get('name', 'Unknown')
        if (i + 1) % 10 == 0 or i == 0 or i == total - 1:
            print(f"    Processing group {i+1}/{total}: {g_name}")
        
        try:
            # Use the STIX ID to avoid unhashable type error
            techniques = mitre_attack_data.get_techniques_used_by_group(group['id'])
            pdf.add_group_section(group, techniques)
        except Exception as e:
            print(f"[-] Error processing group {g_name}: {e}")

    print(f"[*] Saving PDF to {OUTPUT_PDF}...")
    try:
        pdf.output(str(OUTPUT_PDF))
        print(f"[+] Successfully generated PDF report: {OUTPUT_PDF}")
    except Exception as e:
        print(f"[-] Error saving PDF: {e}")

if __name__ == "__main__":
    main()

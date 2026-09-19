"""
SkillsEngine for JARVIS (Antigravity Skills System Integration)
Discovers, indexes, and activates modular skill packages formatted with YAML frontmatter.
Supports progressive disclosure to conserve LLM context tokens.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any


class Skill:
    def __init__(
        self,
        name: str,
        description: str,
        path: str,
        content: str,
        category: str = "general",
        references: Optional[Dict[str, str]] = None
    ):
        self.name = name
        self.description = description
        self.path = path
        self.content = content
        self.category = category
        self.references = references or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "path": self.path,
            "references_count": len(self.references)
        }


class SkillsEngine:
    """
    Manages skills directory discovery, YAML frontmatter parsing,
    progressive disclosure formatting, and dynamic skill learning.
    """

    def __init__(self, skills_dirs: Optional[List[str]] = None):
        self.skills: Dict[str, Skill] = {}
        
        base_dir = Path(__file__).parent.resolve()
        default_dir = base_dir / "skills"
        
        if skills_dirs is not None:
            self.skills_dirs = list(skills_dirs)
        else:
            self.skills_dirs = [str(default_dir)]
                    
        self.discover_skills()

    def discover_skills(self):
        """Scans all configured skill directories for SKILL.md files."""
        self.skills.clear()
        for root_dir in self.skills_dirs:
            p = Path(root_dir)
            if not p.exists():
                continue
            
            # Look for subdirectories containing SKILL.md
            for skill_dir in p.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue
                
                skill = self._parse_skill_file(str(skill_md))
                if skill:
                    self.skills[skill.name] = skill

    def _parse_skill_file(self, filepath: str) -> Optional[Skill]:
        """Parses frontmatter and body from a SKILL.md file."""
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()
            
            # YAML frontmatter regex
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw_text, re.DOTALL)
            if not match:
                # No frontmatter - fallback to file or dir name
                name = Path(filepath).parent.name
                description = f"Skill instructions for {name}"
                body = raw_text
                category = "general"
            else:
                frontmatter_text = match.group(1)
                body = match.group(2)
                try:
                    meta = yaml.safe_load(frontmatter_text) or {}
                except Exception:
                    meta = {}
                name = meta.get("name", Path(filepath).parent.name)
                description = meta.get("description", f"Instructions for {name}").strip()
                category = meta.get("category", "general")
            
            # Collect references from references/ subdir if present
            references = {}
            ref_dir = Path(filepath).parent / "references"
            if ref_dir.exists() and ref_dir.is_dir():
                for ref_file in ref_dir.glob("*.md"):
                    try:
                        with open(ref_file, "r", encoding="utf-8", errors="replace") as rf:
                            references[ref_file.name] = rf.read()
                    except Exception:
                        pass

            return Skill(
                name=name,
                description=description,
                path=filepath,
                content=body.strip(),
                category=category,
                references=references
            )
        except Exception as e:
            print(f"[SKILLS] Error parsing {filepath}: {e}")
            return None

    def list_skills(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns metadata for all discovered skills."""
        results = []
        for s in self.skills.values():
            if category and s.category.lower() != category.lower():
                continue
            results.append(s.to_dict())
        return sorted(results, key=lambda x: x["name"])

    def get_skill(self, name: str) -> Optional[Skill]:
        """Retrieves a skill by name (case-insensitive and hyphen/underscore tolerant)."""
        clean_name = name.strip().lower().replace("_", "-")
        for k, v in self.skills.items():
            if k.lower().replace("_", "-") == clean_name:
                return v
        return None

    def activate_skill(self, name: str) -> str:
        """Returns full markdown instructions and references for a skill."""
        skill = self.get_skill(name)
        if not skill:
            return f"Error: Skill '{name}' not found. Available skills: {', '.join(sorted(self.skills.keys()))}"
        
        output = [
            f"# Activated Skill: {skill.name}",
            f"**Description**: {skill.description}\n",
            "## Instructions",
            skill.content
        ]
        
        if skill.references:
            output.append("\n## Subordinate Reference Documentation")
            for ref_name, ref_content in skill.references.items():
                output.append(f"### Reference: {ref_name}\n{ref_content}")
                
        return "\n\n".join(output)

    def create_skill(
        self,
        name: str,
        description: str,
        instructions: str,
        category: str = "general"
    ) -> str:
        """Dynamically learns and persists a new skill on disk."""
        clean_name = re.sub(r"[^a-zA-Z0-9\-_]", "-", name.strip().lower()).strip("-")
        if not clean_name:
            return "Error: Invalid skill name."
        
        target_dir = Path(self.skills_dirs[0]) / clean_name
        target_dir.mkdir(parents=True, exist_ok=True)
        
        frontmatter = {
            "name": clean_name,
            "description": description.strip(),
            "category": category.strip()
        }
        
        content = (
            f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n"
            f"# {clean_name.replace('-', ' ').title()}\n\n"
            f"{instructions.strip()}\n"
        )
        
        skill_file = target_dir / "SKILL.md"
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Re-index
        new_skill = self._parse_skill_file(str(skill_file))
        if new_skill:
            self.skills[new_skill.name] = new_skill
            return f"Successfully created and indexed skill '{clean_name}' at {skill_file}."
        return f"Created {skill_file} but failed to index."

    def format_prompt_skills_xml(self) -> str:
        """
        Formats skills into the progressive disclosure XML block for LLM system prompt.
        Antigravity pattern: provides names & descriptions so the agent knows when to activate.
        """
        if not self.skills:
            return ""
        
        lines = [
            "<skills>",
            "You can use specialized 'skills' to help you with complex tasks. Each skill has a name and a description listed below.",
            "Skills are folders of instructions, scripts, and resources that extend your capabilities for specialized tasks.",
            "To view the full instructions for any skill, call the `activate_skill` tool with the skill's name.",
            "",
            "Available skills:"
        ]
        
        for name, skill in sorted(self.skills.items()):
            lines.append(f"- {skill.name}: {skill.description}")
            
        lines.append("</skills>")
        return "\n".join(lines)


# Singleton instance
_skills_engine: Optional[SkillsEngine] = None

def get_skills_engine() -> SkillsEngine:
    global _skills_engine
    if _skills_engine is None:
        _skills_engine = SkillsEngine()
    return _skills_engine

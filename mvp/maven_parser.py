"""
Maven POM parser for MVP.
Simplified Maven dependency extraction and analysis.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import xml.etree.ElementTree as ET
import re

import xmltodict

logger = logging.getLogger(__name__)


class MavenParser:
    """Simplified Maven POM parser for MVP."""
    
    def __init__(self):
        self.namespace_pattern = re.compile(r'\{[^}]*\}')
        
    def find_pom_files(self, repo_path: str) -> List[Path]:
        """Find all pom.xml files in a repository."""
        repo_path = Path(repo_path)
        pom_files = []
        
        # Look for pom.xml files
        for pom_file in repo_path.rglob("pom.xml"):
            # Skip test directories and target directories
            if any(part in ['test', 'target', '.git'] for part in pom_file.parts):
                continue
            pom_files.append(pom_file)
        
        logger.info(f"Found {len(pom_files)} POM files in {repo_path}")
        return pom_files
    
    def parse_pom(self, pom_path: Path) -> Optional[Dict[str, Any]]:
        """Parse a single POM file."""
        try:
            with open(pom_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse XML using xmltodict for easier access
            pom_dict = xmltodict.parse(content)
            project = pom_dict.get('project', {})
            
            # Extract basic project information
            artifact_info = self._extract_artifact_info(project)
            dependencies = self._extract_dependencies(project)
            parent_info = self._extract_parent_info(project)
            properties = self._extract_properties(project)
            
            return {
                'file_path': str(pom_path),
                'artifact': artifact_info,
                'dependencies': dependencies,
                'parent': parent_info,
                'properties': properties,
                'modules': self._extract_modules(project)
            }
            
        except Exception as e:
            logger.error(f"Failed to parse POM file {pom_path}: {e}")
            return None
    
    def _extract_artifact_info(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """Extract artifact information from project."""
        group_id = project.get('groupId', '')
        artifact_id = project.get('artifactId', '')
        version = project.get('version', '')
        packaging = project.get('packaging', 'jar')
        
        # Handle parent inheritance
        if not group_id and 'parent' in project:
            group_id = project['parent'].get('groupId', '')
        
        if not version and 'parent' in project:
            version = project['parent'].get('version', '')
        
        return {
            'group_id': group_id,
            'artifact_id': artifact_id,
            'version': version,
            'packaging': packaging,
            'name': project.get('name', artifact_id),
            'description': project.get('description', '')
        }
    
    def _extract_dependencies(self, project: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract dependencies from project."""
        dependencies = []
        
        # Direct dependencies
        deps_section = project.get('dependencies')
        if deps_section:
            dep_list = deps_section.get('dependency', [])
            if isinstance(dep_list, dict):
                dep_list = [dep_list]
            
            for dep in dep_list:
                dependency = self._parse_dependency(dep)
                if dependency:
                    dependencies.append(dependency)
        
        # Dependency management
        dep_mgmt = project.get('dependencyManagement', {}).get('dependencies')
        if dep_mgmt:
            dep_list = dep_mgmt.get('dependency', [])
            if isinstance(dep_list, dict):
                dep_list = [dep_list]
            
            for dep in dep_list:
                dependency = self._parse_dependency(dep, managed=True)
                if dependency:
                    dependencies.append(dependency)
        
        return dependencies
    
    def _parse_dependency(self, dep: Dict[str, Any], managed: bool = False) -> Optional[Dict[str, Any]]:
        """Parse a single dependency."""
        try:
            group_id = dep.get('groupId', '')
            artifact_id = dep.get('artifactId', '')
            version = dep.get('version', '')
            scope = dep.get('scope', 'compile')
            optional = dep.get('optional', 'false').lower() == 'true'
            
            if not group_id or not artifact_id:
                return None
            
            dependency = {
                'group_id': group_id,
                'artifact_id': artifact_id,
                'version': version,
                'scope': scope,
                'optional': optional,
                'managed': managed
            }
            
            # Handle exclusions
            exclusions = dep.get('exclusions')
            if exclusions:
                exclusion_list = exclusions.get('exclusion', [])
                if isinstance(exclusion_list, dict):
                    exclusion_list = [exclusion_list]
                
                dependency['exclusions'] = [
                    {
                        'group_id': exc.get('groupId', ''),
                        'artifact_id': exc.get('artifactId', '')
                    }
                    for exc in exclusion_list
                ]
            
            return dependency
            
        except Exception as e:
            logger.warning(f"Failed to parse dependency: {e}")
            return None
    
    def _extract_parent_info(self, project: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract parent information."""
        parent = project.get('parent')
        if not parent:
            return None
        
        return {
            'group_id': parent.get('groupId', ''),
            'artifact_id': parent.get('artifactId', ''),
            'version': parent.get('version', ''),
            'relative_path': parent.get('relativePath', '../pom.xml')
        }
    
    def _extract_properties(self, project: Dict[str, Any]) -> Dict[str, str]:
        """Extract properties from project."""
        properties = project.get('properties', {})
        
        # Convert all values to strings
        result = {}
        for key, value in properties.items():
            if isinstance(value, dict):
                continue  # Skip complex nested properties
            result[key] = str(value)
        
        return result
    
    def _extract_modules(self, project: Dict[str, Any]) -> List[str]:
        """Extract module information for multi-module projects."""
        modules = project.get('modules')
        if not modules:
            return []
        
        module_list = modules.get('module', [])
        if isinstance(module_list, str):
            module_list = [module_list]
        
        return module_list
    
    def resolve_properties(self, value: str, properties: Dict[str, str]) -> str:
        """Resolve property placeholders in values."""
        if not value or '${' not in value:
            return value
        
        # Simple property resolution
        for prop_name, prop_value in properties.items():
            placeholder = f'${{{prop_name}}}'
            value = value.replace(placeholder, prop_value)
        
        return value
    
    def build_dependency_tree(self, pom_files: List[Path]) -> Dict[str, Any]:
        """Build a dependency tree from multiple POM files."""
        artifacts = {}
        dependencies = []
        
        for pom_file in pom_files:
            pom_data = self.parse_pom(pom_file)
            if not pom_data:
                continue
            
            artifact = pom_data['artifact']
            artifact_id = f"{artifact['group_id']}:{artifact['artifact_id']}:{artifact['version']}"
            
            # Store artifact info
            artifacts[artifact_id] = {
                **artifact,
                'file_path': pom_data['file_path'],
                'properties': pom_data['properties'],
                'parent': pom_data['parent'],
                'modules': pom_data['modules']
            }
            
            # Store dependencies
            for dep in pom_data['dependencies']:
                # Resolve properties in dependency
                resolved_dep = self._resolve_dependency_properties(dep, pom_data['properties'])
                
                dependencies.append({
                    'from_artifact': artifact_id,
                    'to_group_id': resolved_dep['group_id'],
                    'to_artifact_id': resolved_dep['artifact_id'],
                    'to_version': resolved_dep['version'],
                    'scope': resolved_dep['scope'],
                    'optional': resolved_dep['optional'],
                    'managed': resolved_dep['managed'],
                    'exclusions': resolved_dep.get('exclusions', [])
                })
        
        return {
            'artifacts': artifacts,
            'dependencies': dependencies
        }
    
    def _resolve_dependency_properties(self, dep: Dict[str, Any], properties: Dict[str, str]) -> Dict[str, Any]:
        """Resolve properties in a dependency."""
        resolved = dep.copy()
        
        # Resolve common fields
        for field in ['group_id', 'artifact_id', 'version']:
            if field in resolved:
                resolved[field] = self.resolve_properties(resolved[field], properties)
        
        return resolved
    
    def find_dependency_conflicts(self, dependency_tree: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find conflicting dependencies."""
        conflicts = []
        
        # Group dependencies by group_id:artifact_id
        dep_groups = {}
        for dep in dependency_tree['dependencies']:
            key = f"{dep['to_group_id']}:{dep['to_artifact_id']}"
            if key not in dep_groups:
                dep_groups[key] = []
            dep_groups[key].append(dep)
        
        # Find conflicts
        for key, deps in dep_groups.items():
            versions = set(dep['to_version'] for dep in deps if dep['to_version'])
            if len(versions) > 1:
                conflicts.append({
                    'group_artifact': key,
                    'conflicting_versions': list(versions),
                    'dependencies': deps
                })
        
        return conflicts
    
    def get_transitive_dependencies(
        self, 
        artifact_id: str, 
        dependency_tree: Dict[str, Any],
        visited: Set[str] = None,
        max_depth: int = 10
    ) -> List[str]:
        """Get transitive dependencies for an artifact."""
        if visited is None:
            visited = set()
        
        if artifact_id in visited or max_depth <= 0:
            return []
        
        visited.add(artifact_id)
        transitive_deps = []
        
        # Find direct dependencies
        for dep in dependency_tree['dependencies']:
            if dep['from_artifact'] == artifact_id:
                to_artifact = f"{dep['to_group_id']}:{dep['to_artifact_id']}:{dep['to_version']}"
                transitive_deps.append(to_artifact)
                
                # Recursively get dependencies
                nested_deps = self.get_transitive_dependencies(
                    to_artifact, 
                    dependency_tree, 
                    visited.copy(),
                    max_depth - 1
                )
                transitive_deps.extend(nested_deps)
        
        return list(set(transitive_deps))  # Remove duplicates
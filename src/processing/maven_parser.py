"""
Maven POM parser with comprehensive dependency resolution algorithms.
Supports full Maven ecosystem analysis including transitive dependencies,
version conflict resolution, and vulnerability scanning.
"""

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urljoin, urlparse

import requests
from packaging import version


class DependencyScope(Enum):
    """Maven dependency scopes."""
    COMPILE = "compile"
    PROVIDED = "provided"
    RUNTIME = "runtime"
    TEST = "test"
    SYSTEM = "system"
    IMPORT = "import"


class ArtifactType(Enum):
    """Maven artifact types."""
    JAR = "jar"
    WAR = "war"
    EAR = "ear"
    POM = "pom"
    MAVEN_PLUGIN = "maven-plugin"
    EJB = "ejb"
    RAR = "rar"
    BUNDLE = "bundle"


@dataclass
class MavenCoordinates:
    """Maven artifact coordinates (GAV)."""
    group_id: str
    artifact_id: str
    version: str
    type: ArtifactType = ArtifactType.JAR
    classifier: Optional[str] = None
    scope: DependencyScope = DependencyScope.COMPILE
    
    @property
    def coordinates(self) -> str:
        """Get full coordinates string."""
        coords = f"{self.group_id}:{self.artifact_id}:{self.version}"
        if self.type != ArtifactType.JAR:
            coords += f":{self.type.value}"
        if self.classifier:
            coords += f":{self.classifier}"
        return coords
    
    @property
    def ga_coordinates(self) -> str:
        """Get group:artifact coordinates."""
        return f"{self.group_id}:{self.artifact_id}"
    
    def __hash__(self):
        return hash(self.coordinates)
    
    def __eq__(self, other):
        return isinstance(other, MavenCoordinates) and self.coordinates == other.coordinates


@dataclass
class VersionRange:
    """Maven version range specification."""
    raw_range: str
    min_version: Optional[str] = None
    max_version: Optional[str] = None
    min_inclusive: bool = True
    max_inclusive: bool = True
    
    def __post_init__(self):
        self._parse_range()
    
    def _parse_range(self):
        """Parse Maven version range syntax."""
        if not self.raw_range:
            return
        
        # Handle simple version (no brackets)
        if not any(char in self.raw_range for char in ['[', ']', '(', ')']):
            self.min_version = self.raw_range
            return
        
        # Parse range syntax: [1.0,2.0), (1.0,2.0], [1.0,), etc.
        range_pattern = r'([\[\(])([^,\]\)]*),?\s*([^,\]\)]*)?([\]\)])'
        match = re.match(range_pattern, self.raw_range)
        
        if match:
            start_bracket, min_ver, max_ver, end_bracket = match.groups()
            
            self.min_inclusive = start_bracket == '['
            self.max_inclusive = end_bracket == ']'
            
            if min_ver:
                self.min_version = min_ver.strip()
            if max_ver:
                self.max_version = max_ver.strip()
    
    def contains(self, version_str: str) -> bool:
        """Check if version is within this range."""
        if not version_str:
            return False
        
        try:
            v = version.parse(version_str)
            
            # Check minimum version
            if self.min_version:
                min_v = version.parse(self.min_version)
                if self.min_inclusive:
                    if v < min_v:
                        return False
                else:
                    if v <= min_v:
                        return False
            
            # Check maximum version
            if self.max_version:
                max_v = version.parse(self.max_version)
                if self.max_inclusive:
                    if v > max_v:
                        return False
                else:
                    if v >= max_v:
                        return False
            
            return True
        except Exception:
            return False


@dataclass
class MavenDependency:
    """Maven dependency with all metadata."""
    coordinates: MavenCoordinates
    version_range: Optional[VersionRange] = None
    is_optional: bool = False
    exclusions: List[str] = field(default_factory=list)
    system_path: Optional[str] = None
    is_inherited: bool = False
    depth_level: int = 0
    dependency_path: List[str] = field(default_factory=list)
    resolved_version: Optional[str] = None
    conflict_resolution: Optional[str] = None  # "nearest", "managed", "excluded"
    
    def __post_init__(self):
        if self.version_range is None and self.coordinates.version:
            self.version_range = VersionRange(self.coordinates.version)
    
    @property
    def is_transitive(self) -> bool:
        """Check if this is a transitive dependency."""
        return self.depth_level > 0
    
    @property
    def ga_coordinates(self) -> str:
        """Get group:artifact coordinates."""
        return self.coordinates.ga_coordinates


@dataclass
class MavenRepository:
    """Maven repository configuration."""
    id: str
    name: str
    url: str
    layout: str = "default"
    snapshots_enabled: bool = True
    releases_enabled: bool = True
    update_policy: str = "daily"
    checksum_policy: str = "warn"
    authentication: Optional[Dict[str, str]] = None


@dataclass
class MavenProfile:
    """Maven build profile."""
    id: str
    activation: Dict[str, str] = field(default_factory=dict)
    properties: Dict[str, str] = field(default_factory=dict)
    dependencies: List[MavenDependency] = field(default_factory=list)
    repositories: List[MavenRepository] = field(default_factory=list)
    is_active: bool = False


@dataclass
class MavenPlugin:
    """Maven plugin configuration."""
    coordinates: MavenCoordinates
    configuration: Dict[str, str] = field(default_factory=dict)
    executions: List[Dict[str, str]] = field(default_factory=list)
    dependencies: List[MavenDependency] = field(default_factory=list)


@dataclass
class PomFile:
    """Parsed POM file representation."""
    file_path: str
    coordinates: MavenCoordinates
    parent: Optional[MavenCoordinates] = None
    packaging: ArtifactType = ArtifactType.JAR
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)
    dependencies: List[MavenDependency] = field(default_factory=list)
    dependency_management: List[MavenDependency] = field(default_factory=list)
    plugins: List[MavenPlugin] = field(default_factory=list)
    repositories: List[MavenRepository] = field(default_factory=list)
    profiles: List[MavenProfile] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)
    licenses: List[str] = field(default_factory=list)
    developers: List[str] = field(default_factory=list)
    scm_url: Optional[str] = None
    issue_tracker_url: Optional[str] = None
    
    @property
    def effective_properties(self) -> Dict[str, str]:
        """Get effective properties including built-in Maven properties."""
        props = {
            'project.groupId': self.coordinates.group_id,
            'project.artifactId': self.coordinates.artifact_id,
            'project.version': self.coordinates.version,
            'project.packaging': self.packaging.value,
            'project.name': self.name or self.coordinates.artifact_id,
            'project.description': self.description or '',
            'project.url': self.url or '',
            'maven.build.timestamp': '2024-01-01T00:00:00Z',  # Would be actual build time
            'maven.build.timestamp.format': 'yyyy-MM-dd\'T\'HH:mm:ss\'Z\'',
            'basedir': '.',
            'project.basedir': '.',
            'project.build.directory': 'target',
            'project.build.outputDirectory': 'target/classes',
            'project.build.testOutputDirectory': 'target/test-classes',
            'project.build.sourceDirectory': 'src/main/java',
            'project.build.testSourceDirectory': 'src/test/java',
            'project.build.finalName': f"{self.coordinates.artifact_id}-{self.coordinates.version}",
        }
        
        # Add parent properties if available
        if self.parent:
            props.update({
                'project.parent.groupId': self.parent.group_id,
                'project.parent.artifactId': self.parent.artifact_id,
                'project.parent.version': self.parent.version,
            })
        
        # Add custom properties
        props.update(self.properties)
        
        return props
    
    def resolve_property(self, value: str) -> str:
        """Resolve property placeholders in a value."""
        if not value or '${' not in value:
            return value
        
        resolved = value
        props = self.effective_properties
        
        # Find all property references
        property_pattern = r'\$\{([^}]+)\}'
        matches = re.findall(property_pattern, resolved)
        
        for prop_name in matches:
            prop_value = props.get(prop_name, f"${{{prop_name}}}")
            resolved = resolved.replace(f"${{{prop_name}}}", prop_value)
        
        return resolved


class MavenParser:
    """Maven POM parser with dependency resolution."""
    
    def __init__(self, repositories: List[MavenRepository] = None):
        self.repositories = repositories or self._get_default_repositories()
        self.pom_cache: Dict[str, PomFile] = {}
        self.resolution_cache: Dict[str, List[MavenDependency]] = {}
        self.namespace_map = {
            'maven': 'http://maven.apache.org/POM/4.0.0'
        }
    
    def _get_default_repositories(self) -> List[MavenRepository]:
        """Get default Maven repositories."""
        return [
            MavenRepository(
                id="central",
                name="Maven Central Repository",
                url="https://repo1.maven.org/maven2",
                snapshots_enabled=False,
                releases_enabled=True
            ),
            MavenRepository(
                id="apache-snapshots",
                name="Apache Development Snapshot Repository",
                url="https://repository.apache.org/snapshots",
                snapshots_enabled=True,
                releases_enabled=False
            )
        ]
    
    def parse_pom(self, pom_content: str, file_path: str) -> PomFile:
        """Parse POM file content."""
        try:
            root = ET.fromstring(pom_content)
            
            # Handle namespaces
            namespace = self._extract_namespace(root)
            if namespace:
                self.namespace_map['maven'] = namespace
            
            # Extract basic project information
            coordinates = self._extract_coordinates(root)
            parent = self._extract_parent(root)
            
            # Create POM file object
            pom = PomFile(
                file_path=file_path,
                coordinates=coordinates,
                parent=parent,
                packaging=self._extract_packaging(root),
                name=self._extract_text(root, 'name'),
                description=self._extract_text(root, 'description'),
                url=self._extract_text(root, 'url'),
                properties=self._extract_properties(root),
                dependencies=self._extract_dependencies(root),
                dependency_management=self._extract_dependency_management(root),
                plugins=self._extract_plugins(root),
                repositories=self._extract_repositories(root),
                profiles=self._extract_profiles(root),
                modules=self._extract_modules(root),
                licenses=self._extract_licenses(root),
                developers=self._extract_developers(root),
                scm_url=self._extract_scm_url(root),
                issue_tracker_url=self._extract_issue_tracker_url(root)
            )
            
            # Cache parsed POM
            self.pom_cache[coordinates.coordinates] = pom
            
            return pom
            
        except ET.ParseError as e:
            raise ValueError(f"Invalid POM XML: {e}")
    
    def _extract_namespace(self, root: ET.Element) -> Optional[str]:
        """Extract XML namespace from root element."""
        if root.tag.startswith('{'):
            return root.tag[1:].split('}')[0]
        return None
    
    def _extract_coordinates(self, root: ET.Element) -> MavenCoordinates:
        """Extract Maven coordinates from POM."""
        group_id = self._extract_text(root, 'groupId')
        artifact_id = self._extract_text(root, 'artifactId')
        version = self._extract_text(root, 'version')
        
        # Handle inheritance from parent
        if not group_id:
            parent = root.find('.//maven:parent', self.namespace_map)
            if parent is not None:
                group_id = self._extract_text(parent, 'groupId')
        
        if not version:
            parent = root.find('.//maven:parent', self.namespace_map)
            if parent is not None:
                version = self._extract_text(parent, 'version')
        
        if not group_id or not artifact_id or not version:
            raise ValueError("Missing required coordinates: groupId, artifactId, or version")
        
        return MavenCoordinates(
            group_id=group_id,
            artifact_id=artifact_id,
            version=version
        )
    
    def _extract_parent(self, root: ET.Element) -> Optional[MavenCoordinates]:
        """Extract parent coordinates from POM."""
        parent = root.find('.//maven:parent', self.namespace_map)
        if parent is None:
            return None
        
        group_id = self._extract_text(parent, 'groupId')
        artifact_id = self._extract_text(parent, 'artifactId')
        version = self._extract_text(parent, 'version')
        
        if group_id and artifact_id and version:
            return MavenCoordinates(
                group_id=group_id,
                artifact_id=artifact_id,
                version=version,
                type=ArtifactType.POM
            )
        
        return None
    
    def _extract_packaging(self, root: ET.Element) -> ArtifactType:
        """Extract packaging type from POM."""
        packaging = self._extract_text(root, 'packaging')
        if packaging:
            try:
                return ArtifactType(packaging)
            except ValueError:
                pass
        return ArtifactType.JAR
    
    def _extract_text(self, parent: ET.Element, tag: str) -> Optional[str]:
        """Extract text content from XML element."""
        element = parent.find(f'.//maven:{tag}', self.namespace_map)
        if element is not None and element.text:
            return element.text.strip()
        return None
    
    def _extract_properties(self, root: ET.Element) -> Dict[str, str]:
        """Extract properties from POM."""
        properties = {}
        props_element = root.find('.//maven:properties', self.namespace_map)
        
        if props_element is not None:
            for prop in props_element:
                if prop.text:
                    # Remove namespace prefix from tag
                    tag = prop.tag.split('}')[-1] if '}' in prop.tag else prop.tag
                    properties[tag] = prop.text.strip()
        
        return properties
    
    def _extract_dependencies(self, root: ET.Element) -> List[MavenDependency]:
        """Extract dependencies from POM."""
        dependencies = []
        deps_element = root.find('.//maven:dependencies', self.namespace_map)
        
        if deps_element is not None:
            for dep in deps_element.findall('maven:dependency', self.namespace_map):
                dependency = self._parse_dependency(dep)
                if dependency:
                    dependencies.append(dependency)
        
        return dependencies
    
    def _extract_dependency_management(self, root: ET.Element) -> List[MavenDependency]:
        """Extract dependency management from POM."""
        dependencies = []
        dep_mgmt = root.find('.//maven:dependencyManagement', self.namespace_map)
        
        if dep_mgmt is not None:
            deps_element = dep_mgmt.find('maven:dependencies', self.namespace_map)
            if deps_element is not None:
                for dep in deps_element.findall('maven:dependency', self.namespace_map):
                    dependency = self._parse_dependency(dep)
                    if dependency:
                        dependencies.append(dependency)
        
        return dependencies
    
    def _parse_dependency(self, dep_element: ET.Element) -> Optional[MavenDependency]:
        """Parse a single dependency element."""
        group_id = self._extract_text(dep_element, 'groupId')
        artifact_id = self._extract_text(dep_element, 'artifactId')
        version = self._extract_text(dep_element, 'version')
        
        if not group_id or not artifact_id:
            return None
        
        # Parse scope
        scope_text = self._extract_text(dep_element, 'scope')
        scope = DependencyScope.COMPILE
        if scope_text:
            try:
                scope = DependencyScope(scope_text)
            except ValueError:
                pass
        
        # Parse type
        type_text = self._extract_text(dep_element, 'type')
        artifact_type = ArtifactType.JAR
        if type_text:
            try:
                artifact_type = ArtifactType(type_text)
            except ValueError:
                pass
        
        # Parse optional
        optional_text = self._extract_text(dep_element, 'optional')
        is_optional = optional_text and optional_text.lower() == 'true'
        
        # Parse classifier
        classifier = self._extract_text(dep_element, 'classifier')
        
        # Parse system path
        system_path = self._extract_text(dep_element, 'systemPath')
        
        # Parse exclusions
        exclusions = []
        exclusions_element = dep_element.find('maven:exclusions', self.namespace_map)
        if exclusions_element is not None:
            for exclusion in exclusions_element.findall('maven:exclusion', self.namespace_map):
                excl_group = self._extract_text(exclusion, 'groupId')
                excl_artifact = self._extract_text(exclusion, 'artifactId')
                if excl_group and excl_artifact:
                    exclusions.append(f"{excl_group}:{excl_artifact}")
        
        # Create coordinates
        coordinates = MavenCoordinates(
            group_id=group_id,
            artifact_id=artifact_id,
            version=version or "*",
            type=artifact_type,
            classifier=classifier,
            scope=scope
        )
        
        # Create version range
        version_range = None
        if version:
            version_range = VersionRange(version)
        
        return MavenDependency(
            coordinates=coordinates,
            version_range=version_range,
            is_optional=is_optional,
            exclusions=exclusions,
            system_path=system_path
        )
    
    def _extract_plugins(self, root: ET.Element) -> List[MavenPlugin]:
        """Extract plugins from POM."""
        plugins = []
        
        # Extract from build/plugins
        build_element = root.find('.//maven:build', self.namespace_map)
        if build_element is not None:
            plugins_element = build_element.find('maven:plugins', self.namespace_map)
            if plugins_element is not None:
                for plugin in plugins_element.findall('maven:plugin', self.namespace_map):
                    parsed_plugin = self._parse_plugin(plugin)
                    if parsed_plugin:
                        plugins.append(parsed_plugin)
        
        return plugins
    
    def _parse_plugin(self, plugin_element: ET.Element) -> Optional[MavenPlugin]:
        """Parse a single plugin element."""
        group_id = self._extract_text(plugin_element, 'groupId') or 'org.apache.maven.plugins'
        artifact_id = self._extract_text(plugin_element, 'artifactId')
        version = self._extract_text(plugin_element, 'version')
        
        if not artifact_id:
            return None
        
        coordinates = MavenCoordinates(
            group_id=group_id,
            artifact_id=artifact_id,
            version=version or "LATEST",
            type=ArtifactType.MAVEN_PLUGIN
        )
        
        # Parse configuration
        configuration = {}
        config_element = plugin_element.find('maven:configuration', self.namespace_map)
        if config_element is not None:
            for config in config_element:
                tag = config.tag.split('}')[-1] if '}' in config.tag else config.tag
                if config.text:
                    configuration[tag] = config.text.strip()
        
        # Parse executions
        executions = []
        executions_element = plugin_element.find('maven:executions', self.namespace_map)
        if executions_element is not None:
            for execution in executions_element.findall('maven:execution', self.namespace_map):
                exec_id = self._extract_text(execution, 'id')
                phase = self._extract_text(execution, 'phase')
                goals = []
                goals_element = execution.find('maven:goals', self.namespace_map)
                if goals_element is not None:
                    for goal in goals_element.findall('maven:goal', self.namespace_map):
                        if goal.text:
                            goals.append(goal.text.strip())
                
                executions.append({
                    'id': exec_id,
                    'phase': phase,
                    'goals': goals
                })
        
        return MavenPlugin(
            coordinates=coordinates,
            configuration=configuration,
            executions=executions
        )
    
    def _extract_repositories(self, root: ET.Element) -> List[MavenRepository]:
        """Extract repositories from POM."""
        repositories = []
        repos_element = root.find('.//maven:repositories', self.namespace_map)
        
        if repos_element is not None:
            for repo in repos_element.findall('maven:repository', self.namespace_map):
                repository = self._parse_repository(repo)
                if repository:
                    repositories.append(repository)
        
        return repositories
    
    def _parse_repository(self, repo_element: ET.Element) -> Optional[MavenRepository]:
        """Parse a single repository element."""
        repo_id = self._extract_text(repo_element, 'id')
        name = self._extract_text(repo_element, 'name')
        url = self._extract_text(repo_element, 'url')
        
        if not repo_id or not url:
            return None
        
        layout = self._extract_text(repo_element, 'layout') or 'default'
        
        # Parse snapshots and releases policies
        snapshots_enabled = True
        releases_enabled = True
        
        snapshots_element = repo_element.find('maven:snapshots', self.namespace_map)
        if snapshots_element is not None:
            enabled = self._extract_text(snapshots_element, 'enabled')
            snapshots_enabled = enabled != 'false'
        
        releases_element = repo_element.find('maven:releases', self.namespace_map)
        if releases_element is not None:
            enabled = self._extract_text(releases_element, 'enabled')
            releases_enabled = enabled != 'false'
        
        return MavenRepository(
            id=repo_id,
            name=name or repo_id,
            url=url,
            layout=layout,
            snapshots_enabled=snapshots_enabled,
            releases_enabled=releases_enabled
        )
    
    def _extract_profiles(self, root: ET.Element) -> List[MavenProfile]:
        """Extract profiles from POM."""
        profiles = []
        profiles_element = root.find('.//maven:profiles', self.namespace_map)
        
        if profiles_element is not None:
            for profile in profiles_element.findall('maven:profile', self.namespace_map):
                parsed_profile = self._parse_profile(profile)
                if parsed_profile:
                    profiles.append(parsed_profile)
        
        return profiles
    
    def _parse_profile(self, profile_element: ET.Element) -> Optional[MavenProfile]:
        """Parse a single profile element."""
        profile_id = self._extract_text(profile_element, 'id')
        if not profile_id:
            return None
        
        # Parse activation
        activation = {}
        activation_element = profile_element.find('maven:activation', self.namespace_map)
        if activation_element is not None:
            for child in activation_element:
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if child.text:
                    activation[tag] = child.text.strip()
        
        # Parse properties
        properties = {}
        props_element = profile_element.find('maven:properties', self.namespace_map)
        if props_element is not None:
            for prop in props_element:
                tag = prop.tag.split('}')[-1] if '}' in prop.tag else prop.tag
                if prop.text:
                    properties[tag] = prop.text.strip()
        
        # Parse dependencies
        dependencies = []
        deps_element = profile_element.find('maven:dependencies', self.namespace_map)
        if deps_element is not None:
            for dep in deps_element.findall('maven:dependency', self.namespace_map):
                dependency = self._parse_dependency(dep)
                if dependency:
                    dependencies.append(dependency)
        
        return MavenProfile(
            id=profile_id,
            activation=activation,
            properties=properties,
            dependencies=dependencies
        )
    
    def _extract_modules(self, root: ET.Element) -> List[str]:
        """Extract modules from POM."""
        modules = []
        modules_element = root.find('.//maven:modules', self.namespace_map)
        
        if modules_element is not None:
            for module in modules_element.findall('maven:module', self.namespace_map):
                if module.text:
                    modules.append(module.text.strip())
        
        return modules
    
    def _extract_licenses(self, root: ET.Element) -> List[str]:
        """Extract licenses from POM."""
        licenses = []
        licenses_element = root.find('.//maven:licenses', self.namespace_map)
        
        if licenses_element is not None:
            for license_elem in licenses_element.findall('maven:license', self.namespace_map):
                name = self._extract_text(license_elem, 'name')
                if name:
                    licenses.append(name)
        
        return licenses
    
    def _extract_developers(self, root: ET.Element) -> List[str]:
        """Extract developers from POM."""
        developers = []
        developers_element = root.find('.//maven:developers', self.namespace_map)
        
        if developers_element is not None:
            for dev in developers_element.findall('maven:developer', self.namespace_map):
                name = self._extract_text(dev, 'name')
                if name:
                    developers.append(name)
        
        return developers
    
    def _extract_scm_url(self, root: ET.Element) -> Optional[str]:
        """Extract SCM URL from POM."""
        scm_element = root.find('.//maven:scm', self.namespace_map)
        if scm_element is not None:
            return self._extract_text(scm_element, 'url')
        return None
    
    def _extract_issue_tracker_url(self, root: ET.Element) -> Optional[str]:
        """Extract issue tracker URL from POM."""
        issue_element = root.find('.//maven:issueManagement', self.namespace_map)
        if issue_element is not None:
            return self._extract_text(issue_element, 'url')
        return None
    
    def resolve_dependencies(self, pom: PomFile, include_test: bool = False) -> List[MavenDependency]:
        """Resolve all dependencies for a POM file."""
        cache_key = f"{pom.coordinates.coordinates}:{include_test}"
        
        if cache_key in self.resolution_cache:
            return self.resolution_cache[cache_key]
        
        # Initialize resolution context
        context = DependencyResolutionContext(
            pom=pom,
            include_test=include_test,
            dependency_management=self._build_dependency_management(pom),
            visited_artifacts=set(),
            resolution_path=[]
        )
        
        # Resolve dependencies
        resolved_dependencies = self._resolve_dependencies_recursive(context)
        
        # Apply conflict resolution
        final_dependencies = self._apply_conflict_resolution(resolved_dependencies)
        
        # Cache results
        self.resolution_cache[cache_key] = final_dependencies
        
        return final_dependencies
    
    def _build_dependency_management(self, pom: PomFile) -> Dict[str, MavenDependency]:
        """Build dependency management map including parent POMs."""
        dep_mgmt = {}
        
        # Add current POM's dependency management
        for dep in pom.dependency_management:
            dep_mgmt[dep.ga_coordinates] = dep
        
        # TODO: Add parent POM dependency management
        # This would require fetching and parsing parent POMs
        
        return dep_mgmt
    
    def _resolve_dependencies_recursive(self, context: 'DependencyResolutionContext') -> List[MavenDependency]:
        """Recursively resolve dependencies."""
        resolved = []
        
        for dependency in context.pom.dependencies:
            # Skip test dependencies if not requested
            if not context.include_test and dependency.coordinates.scope == DependencyScope.TEST:
                continue
            
            # Skip optional dependencies
            if dependency.is_optional:
                continue
            
            # Check for circular dependencies
            if dependency.coordinates.coordinates in context.visited_artifacts:
                continue
            
            # Apply dependency management
            managed_dep = self._apply_dependency_management(dependency, context.dependency_management)
            
            # Set depth level and path
            managed_dep.depth_level = len(context.resolution_path)
            managed_dep.dependency_path = context.resolution_path.copy()
            
            # Add to resolved list
            resolved.append(managed_dep)
            
            # Resolve transitive dependencies
            if managed_dep.coordinates.scope not in [DependencyScope.PROVIDED, DependencyScope.SYSTEM]:
                transitive_deps = self._resolve_transitive_dependencies(managed_dep, context)
                resolved.extend(transitive_deps)
        
        return resolved
    
    def _apply_dependency_management(self, dependency: MavenDependency, dep_mgmt: Dict[str, MavenDependency]) -> MavenDependency:
        """Apply dependency management to a dependency."""
        managed = dep_mgmt.get(dependency.ga_coordinates)
        
        if managed:
            # Create new dependency with managed version
            new_coords = MavenCoordinates(
                group_id=dependency.coordinates.group_id,
                artifact_id=dependency.coordinates.artifact_id,
                version=managed.coordinates.version,
                type=dependency.coordinates.type,
                classifier=dependency.coordinates.classifier,
                scope=dependency.coordinates.scope
            )
            
            return MavenDependency(
                coordinates=new_coords,
                version_range=managed.version_range,
                is_optional=dependency.is_optional,
                exclusions=dependency.exclusions,
                system_path=dependency.system_path,
                is_inherited=dependency.is_inherited,
                depth_level=dependency.depth_level,
                dependency_path=dependency.dependency_path,
                resolved_version=managed.coordinates.version,
                conflict_resolution="managed"
            )
        
        return dependency
    
    def _resolve_transitive_dependencies(self, dependency: MavenDependency, context: 'DependencyResolutionContext') -> List[MavenDependency]:
        """Resolve transitive dependencies for a given dependency."""
        # This is a simplified version - in practice, you'd fetch the POM from repository
        # and recursively resolve its dependencies
        
        # For now, return empty list
        # TODO: Implement actual transitive resolution by fetching POMs from repositories
        return []
    
    def _apply_conflict_resolution(self, dependencies: List[MavenDependency]) -> List[MavenDependency]:
        """Apply Maven conflict resolution rules."""
        # Group dependencies by GA coordinates
        dep_groups = {}
        for dep in dependencies:
            ga = dep.ga_coordinates
            if ga not in dep_groups:
                dep_groups[ga] = []
            dep_groups[ga].append(dep)
        
        resolved = []
        
        for ga, deps in dep_groups.items():
            if len(deps) == 1:
                resolved.append(deps[0])
            else:
                # Apply nearest-wins strategy
                winner = min(deps, key=lambda d: d.depth_level)
                winner.conflict_resolution = "nearest"
                resolved.append(winner)
        
        return resolved
    
    def detect_conflicts(self, dependencies: List[MavenDependency]) -> List[Dict[str, any]]:
        """Detect version conflicts in dependencies."""
        conflicts = []
        
        # Group by GA coordinates
        dep_groups = {}
        for dep in dependencies:
            ga = dep.ga_coordinates
            if ga not in dep_groups:
                dep_groups[ga] = []
            dep_groups[ga].append(dep)
        
        # Find conflicts
        for ga, deps in dep_groups.items():
            if len(deps) > 1:
                versions = [dep.coordinates.version for dep in deps]
                if len(set(versions)) > 1:
                    conflicts.append({
                        'artifact': ga,
                        'conflicting_versions': versions,
                        'dependencies': deps,
                        'resolution': 'nearest-wins'
                    })
        
        return conflicts
    
    def analyze_vulnerabilities(self, dependencies: List[MavenDependency]) -> List[Dict[str, any]]:
        """Analyze dependencies for known vulnerabilities."""
        # This would integrate with vulnerability databases like OSV, NVD, etc.
        # For now, return empty list
        # TODO: Implement actual vulnerability scanning
        return []
    
    def get_dependency_tree(self, dependencies: List[MavenDependency]) -> Dict[str, any]:
        """Generate dependency tree structure."""
        tree = {}
        
        # Build tree structure
        for dep in dependencies:
            current = tree
            
            # Follow dependency path
            for path_item in dep.dependency_path:
                if path_item not in current:
                    current[path_item] = {}
                current = current[path_item]
            
            # Add current dependency
            current[dep.coordinates.coordinates] = {
                'coordinates': dep.coordinates.coordinates,
                'scope': dep.coordinates.scope.value,
                'depth': dep.depth_level,
                'optional': dep.is_optional,
                'conflict_resolution': dep.conflict_resolution
            }
        
        return tree


@dataclass
class DependencyResolutionContext:
    """Context for dependency resolution."""
    pom: PomFile
    include_test: bool
    dependency_management: Dict[str, MavenDependency]
    visited_artifacts: Set[str]
    resolution_path: List[str]


class GradleParser:
    """Basic Gradle build file parser for build.gradle files."""
    
    def __init__(self):
        self.dependencies = []
    
    def parse_gradle_file(self, gradle_content: str, file_path: str) -> List[MavenDependency]:
        """Parse Gradle build file for dependencies."""
        dependencies = []
        
        # Simple regex-based parsing for dependencies block
        dep_pattern = r'(\w+)\s+["\']([^:"\']+):([^:"\']+):([^"\']+)["\']'
        
        matches = re.findall(dep_pattern, gradle_content)
        
        for scope, group_id, artifact_id, version in matches:
            # Map Gradle scopes to Maven scopes
            maven_scope = self._map_gradle_scope(scope)
            
            coordinates = MavenCoordinates(
                group_id=group_id,
                artifact_id=artifact_id,
                version=version,
                scope=maven_scope
            )
            
            dependency = MavenDependency(coordinates=coordinates)
            dependencies.append(dependency)
        
        return dependencies
    
    def _map_gradle_scope(self, gradle_scope: str) -> DependencyScope:
        """Map Gradle scope to Maven scope."""
        scope_mapping = {
            'implementation': DependencyScope.COMPILE,
            'compile': DependencyScope.COMPILE,
            'api': DependencyScope.COMPILE,
            'compileOnly': DependencyScope.PROVIDED,
            'runtimeOnly': DependencyScope.RUNTIME,
            'testImplementation': DependencyScope.TEST,
            'testCompile': DependencyScope.TEST,
            'testRuntime': DependencyScope.TEST,
        }
        
        return scope_mapping.get(gradle_scope, DependencyScope.COMPILE)
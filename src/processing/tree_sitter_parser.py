"""
Tree-sitter AST parsing pipeline for multi-language code analysis.
Provides syntax-aware chunking and business logic extraction.
"""

import ast
import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import tree_sitter_languages
from tree_sitter import Language, Node, Parser, Tree


class SupportedLanguage(Enum):
    """Supported programming languages for AST parsing."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    CPP = "cpp"
    C_SHARP = "c_sharp"
    RUBY = "ruby"
    PHP = "php"
    KOTLIN = "kotlin"
    SWIFT = "swift"
    JSP = "jsp"
    XML = "xml"


@dataclass
class CodeChunk:
    """Represents a semantically meaningful chunk of code."""
    id: str
    content: str
    language: SupportedLanguage
    chunk_type: str  # function, class, method, variable, etc.
    name: Optional[str]
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    parent_id: Optional[str] = None
    children_ids: List[str] = None
    imports: List[str] = None
    dependencies: List[str] = None
    docstring: Optional[str] = None
    annotations: Dict[str, Any] = None
    complexity_score: float = 0.0
    business_rules: List[str] = None
    framework_patterns: Dict[str, Any] = None
    migration_notes: List[str] = None
    
    def __post_init__(self):
        if self.children_ids is None:
            self.children_ids = []
        if self.imports is None:
            self.imports = []
        if self.dependencies is None:
            self.dependencies = []
        if self.annotations is None:
            self.annotations = {}
        if self.business_rules is None:
            self.business_rules = []
        if self.framework_patterns is None:
            self.framework_patterns = {}
        if self.migration_notes is None:
            self.migration_notes = []


@dataclass
class RelationshipInfo:
    """Represents relationships between code entities."""
    source_id: str
    target_id: str
    relationship_type: str  # calls, inherits, imports, defines, etc.
    source_location: Tuple[int, int]  # (line, column)
    target_location: Optional[Tuple[int, int]] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class TreeSitterParser:
    """Advanced Tree-sitter parser for multi-language code analysis."""
    
    def __init__(self):
        self.parsers: Dict[SupportedLanguage, Parser] = {}
        self.languages: Dict[SupportedLanguage, Language] = {}
        self._initialize_parsers()
    
    def _initialize_parsers(self):
        """Initialize Tree-sitter parsers for all supported languages."""
        for lang in SupportedLanguage:
            try:
                language = tree_sitter_languages.get_language(lang.value)
                parser = tree_sitter_languages.get_parser(lang.value)
                
                self.languages[lang] = language
                self.parsers[lang] = parser
            except Exception as e:
                print(f"Warning: Failed to initialize parser for {lang.value}: {e}")
    
    def parse_code(self, code: str, language: SupportedLanguage, file_path: str = "") -> Tuple[List[CodeChunk], List[RelationshipInfo]]:
        """
        Parse code into semantic chunks and extract relationships.
        
        Args:
            code: Source code to parse
            language: Programming language
            file_path: Path to the source file
            
        Returns:
            Tuple of (chunks, relationships)
        """
        if language not in self.parsers:
            raise ValueError(f"Unsupported language: {language}")
        
        parser = self.parsers[language]
        tree = parser.parse(code.encode('utf-8'))
        
        chunks = []
        relationships = []
        
        # Language-specific parsing
        if language == SupportedLanguage.PYTHON:
            chunks, relationships = self._parse_python(code, tree, file_path)
        elif language == SupportedLanguage.JAVASCRIPT:
            chunks, relationships = self._parse_javascript(code, tree, file_path)
        elif language == SupportedLanguage.TYPESCRIPT:
            chunks, relationships = self._parse_generic(code, tree, file_path, language)
        elif language == SupportedLanguage.RUST:
            chunks, relationships = self._parse_generic(code, tree, file_path, language)
        elif language == SupportedLanguage.GO:
            chunks, relationships = self._parse_generic(code, tree, file_path, language)
        elif language == SupportedLanguage.JAVA:
            chunks, relationships = self._parse_generic(code, tree, file_path, language)
        elif language == SupportedLanguage.CPP:
            chunks, relationships = self._parse_generic(code, tree, file_path, language)
        elif language == SupportedLanguage.JSP:
            chunks, relationships = self._parse_jsp(code, tree, file_path)
        elif language == SupportedLanguage.XML:
            chunks, relationships = self._parse_xml(code, tree, file_path)
        else:
            # Generic parsing for other languages
            chunks, relationships = self._parse_generic(code, tree, file_path, language)
        
        return chunks, relationships
    
    def _parse_python(self, code: str, tree: Tree, file_path: str) -> Tuple[List[CodeChunk], List[RelationshipInfo]]:
        """Parse Python code with advanced semantic analysis."""
        chunks = []
        relationships = []
        code_lines = code.split('\n')
        
        def traverse_node(node: Node, parent_id: Optional[str] = None) -> None:
            if node.type in ['function_definition', 'class_definition', 'async_function_definition']:
                chunk = self._create_python_chunk(node, code, code_lines, file_path, parent_id)
                chunks.append(chunk)
                
                # Parse function/class body for relationships
                if node.type in ['function_definition', 'async_function_definition']:
                    self._extract_python_function_relationships(node, chunk, code, relationships)
                elif node.type == 'class_definition':
                    self._extract_python_class_relationships(node, chunk, code, relationships)
                
                # Recurse with current chunk as parent
                for child in node.children:
                    traverse_node(child, chunk.id)
            
            elif node.type == 'import_statement' or node.type == 'import_from_statement':
                import_chunk = self._create_python_import_chunk(node, code, code_lines, file_path)
                chunks.append(import_chunk)
                
            else:
                # Continue traversing
                for child in node.children:
                    traverse_node(child, parent_id)
        
        # Start traversal from root
        traverse_node(tree.root_node)
        
        # Add module-level variables and assignments
        self._extract_python_module_level_entities(tree.root_node, code, code_lines, file_path, chunks)
        
        return chunks, relationships
    
    def _create_python_chunk(self, node: Node, code: str, code_lines: List[str], file_path: str, parent_id: Optional[str]) -> CodeChunk:
        """Create a Python code chunk from AST node."""
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        
        # Extract name
        name = None
        for child in node.children:
            if child.type == 'identifier':
                name = self._get_node_text(child, code)
                break
        
        # Extract content
        content = '\n'.join(code_lines[start_line:end_line + 1])
        
        # Generate unique ID
        chunk_id = self._generate_chunk_id(file_path, name or node.type, start_line)
        
        # Extract docstring
        docstring = self._extract_python_docstring(node, code)
        
        # Extract decorators and annotations
        annotations = self._extract_python_annotations(node, code)
        
        # Calculate complexity
        complexity = self._calculate_complexity(content)
        
        return CodeChunk(
            id=chunk_id,
            content=content,
            language=SupportedLanguage.PYTHON,
            chunk_type=node.type,
            name=name,
            start_line=start_line,
            end_line=end_line,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            parent_id=parent_id,
            docstring=docstring,
            annotations=annotations,
            complexity_score=complexity
        )
    
    def _create_python_import_chunk(self, node: Node, code: str, code_lines: List[str], file_path: str) -> CodeChunk:
        """Create a Python import chunk."""
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        
        content = '\n'.join(code_lines[start_line:end_line + 1])
        chunk_id = self._generate_chunk_id(file_path, "import", start_line)
        
        # Extract imported modules
        imports = self._extract_python_imports(node, code)
        
        return CodeChunk(
            id=chunk_id,
            content=content,
            language=SupportedLanguage.PYTHON,
            chunk_type="import",
            name=None,
            start_line=start_line,
            end_line=end_line,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            imports=imports
        )
    
    def _extract_python_function_relationships(self, node: Node, chunk: CodeChunk, code: str, relationships: List[RelationshipInfo]) -> None:
        """Extract relationships from Python function definitions."""
        def find_calls(n: Node) -> None:
            if n.type == 'call':
                # Extract function calls
                for child in n.children:
                    if child.type == 'identifier' or child.type == 'attribute':
                        called_name = self._get_node_text(child, code)
                        relationship = RelationshipInfo(
                            source_id=chunk.id,
                            target_id=f"function:{called_name}",
                            relationship_type="calls",
                            source_location=(chunk.start_line, 0),
                            target_location=(child.start_point[0], child.start_point[1]),
                            metadata={"function_name": called_name}
                        )
                        relationships.append(relationship)
                        break
            
            for child in n.children:
                find_calls(child)
        
        find_calls(node)
    
    def _extract_python_class_relationships(self, node: Node, chunk: CodeChunk, code: str, relationships: List[RelationshipInfo]) -> None:
        """Extract relationships from Python class definitions."""
        # Extract inheritance relationships
        for child in node.children:
            if child.type == 'argument_list':
                for arg in child.children:
                    if arg.type == 'identifier':
                        parent_class = self._get_node_text(arg, code)
                        relationship = RelationshipInfo(
                            source_id=chunk.id,
                            target_id=f"class:{parent_class}",
                            relationship_type="inherits",
                            source_location=(chunk.start_line, 0),
                            metadata={"parent_class": parent_class}
                        )
                        relationships.append(relationship)
    
    def _extract_python_module_level_entities(self, node: Node, code: str, code_lines: List[str], file_path: str, chunks: List[CodeChunk]) -> None:
        """Extract module-level variables and assignments."""
        def find_assignments(n: Node) -> None:
            if n.type == 'assignment':
                start_line = n.start_point[0]
                end_line = n.end_point[0]
                
                # Extract variable names
                for child in n.children:
                    if child.type == 'identifier':
                        var_name = self._get_node_text(child, code)
                        content = '\n'.join(code_lines[start_line:end_line + 1])
                        
                        chunk_id = self._generate_chunk_id(file_path, f"var:{var_name}", start_line)
                        
                        chunk = CodeChunk(
                            id=chunk_id,
                            content=content,
                            language=SupportedLanguage.PYTHON,
                            chunk_type="variable",
                            name=var_name,
                            start_line=start_line,
                            end_line=end_line,
                            start_byte=n.start_byte,
                            end_byte=n.end_byte
                        )
                        chunks.append(chunk)
                        break
            
            for child in n.children:
                find_assignments(child)
        
        find_assignments(node)
    
    def _parse_javascript(self, code: str, tree: Tree, file_path: str) -> Tuple[List[CodeChunk], List[RelationshipInfo]]:
        """Parse JavaScript code with ES6+ support."""
        chunks = []
        relationships = []
        code_lines = code.split('\n')
        
        def traverse_node(node: Node, parent_id: Optional[str] = None) -> None:
            if node.type in ['function_declaration', 'arrow_function', 'function_expression', 'method_definition']:
                chunk = self._create_javascript_chunk(node, code, code_lines, file_path, parent_id)
                chunks.append(chunk)
                
                # Extract function relationships
                self._extract_javascript_function_relationships(node, chunk, code, relationships)
                
                # Recurse with current chunk as parent
                for child in node.children:
                    traverse_node(child, chunk.id)
            
            elif node.type == 'class_declaration':
                chunk = self._create_javascript_class_chunk(node, code, code_lines, file_path, parent_id)
                chunks.append(chunk)
                
                # Extract class relationships
                self._extract_javascript_class_relationships(node, chunk, code, relationships)
                
                # Recurse with current chunk as parent
                for child in node.children:
                    traverse_node(child, chunk.id)
            
            elif node.type in ['import_statement', 'import_clause']:
                import_chunk = self._create_javascript_import_chunk(node, code, code_lines, file_path)
                chunks.append(import_chunk)
            
            else:
                # Continue traversing
                for child in node.children:
                    traverse_node(child, parent_id)
        
        traverse_node(tree.root_node)
        
        # Extract module-level variables and exports
        self._extract_javascript_module_level_entities(tree.root_node, code, code_lines, file_path, chunks)
        
        return chunks, relationships
    
    def _create_javascript_chunk(self, node: Node, code: str, code_lines: List[str], file_path: str, parent_id: Optional[str]) -> CodeChunk:
        """Create a JavaScript function chunk."""
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        
        # Extract function name
        name = None
        if node.type == 'function_declaration':
            for child in node.children:
                if child.type == 'identifier':
                    name = self._get_node_text(child, code)
                    break
        elif node.type == 'method_definition':
            for child in node.children:
                if child.type == 'property_identifier':
                    name = self._get_node_text(child, code)
                    break
        
        content = '\n'.join(code_lines[start_line:end_line + 1])
        chunk_id = self._generate_chunk_id(file_path, name or node.type, start_line)
        
        # Extract JSDoc comments
        docstring = self._extract_javascript_jsdoc(node, code)
        
        # Calculate complexity
        complexity = self._calculate_complexity(content)
        
        return CodeChunk(
            id=chunk_id,
            content=content,
            language=SupportedLanguage.JAVASCRIPT,
            chunk_type=node.type,
            name=name,
            start_line=start_line,
            end_line=end_line,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            parent_id=parent_id,
            docstring=docstring,
            complexity_score=complexity
        )
    
    def _create_javascript_class_chunk(self, node: Node, code: str, code_lines: List[str], file_path: str, parent_id: Optional[str]) -> CodeChunk:
        """Create a JavaScript class chunk."""
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        
        # Extract class name
        name = None
        for child in node.children:
            if child.type == 'identifier':
                name = self._get_node_text(child, code)
                break
        
        content = '\n'.join(code_lines[start_line:end_line + 1])
        chunk_id = self._generate_chunk_id(file_path, name or "class", start_line)
        
        # Extract JSDoc comments
        docstring = self._extract_javascript_jsdoc(node, code)
        
        # Calculate complexity
        complexity = self._calculate_complexity(content)
        
        return CodeChunk(
            id=chunk_id,
            content=content,
            language=SupportedLanguage.JAVASCRIPT,
            chunk_type="class",
            name=name,
            start_line=start_line,
            end_line=end_line,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            parent_id=parent_id,
            docstring=docstring,
            complexity_score=complexity
        )
    
    def _create_javascript_import_chunk(self, node: Node, code: str, code_lines: List[str], file_path: str) -> CodeChunk:
        """Create a JavaScript import chunk."""
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        
        content = '\n'.join(code_lines[start_line:end_line + 1])
        chunk_id = self._generate_chunk_id(file_path, "import", start_line)
        
        # Extract imported modules
        imports = self._extract_javascript_imports(node, code)
        
        return CodeChunk(
            id=chunk_id,
            content=content,
            language=SupportedLanguage.JAVASCRIPT,
            chunk_type="import",
            name=None,
            start_line=start_line,
            end_line=end_line,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            imports=imports
        )
    
    def _extract_javascript_function_relationships(self, node: Node, chunk: CodeChunk, code: str, relationships: List[RelationshipInfo]) -> None:
        """Extract relationships from JavaScript function definitions."""
        def find_calls(n: Node) -> None:
            if n.type == 'call_expression':
                # Extract function calls
                for child in n.children:
                    if child.type == 'identifier' or child.type == 'member_expression':
                        called_name = self._get_node_text(child, code)
                        relationship = RelationshipInfo(
                            source_id=chunk.id,
                            target_id=f"function:{called_name}",
                            relationship_type="calls",
                            source_location=(chunk.start_line, 0),
                            target_location=(child.start_point[0], child.start_point[1]),
                            metadata={"function_name": called_name}
                        )
                        relationships.append(relationship)
                        break
            
            for child in n.children:
                find_calls(child)
        
        find_calls(node)
    
    def _extract_javascript_class_relationships(self, node: Node, chunk: CodeChunk, code: str, relationships: List[RelationshipInfo]) -> None:
        """Extract relationships from JavaScript class definitions."""
        # Extract inheritance relationships
        for child in node.children:
            if child.type == 'class_heritage':
                for heritage_child in child.children:
                    if heritage_child.type == 'identifier':
                        parent_class = self._get_node_text(heritage_child, code)
                        relationship = RelationshipInfo(
                            source_id=chunk.id,
                            target_id=f"class:{parent_class}",
                            relationship_type="extends",
                            source_location=(chunk.start_line, 0),
                            metadata={"parent_class": parent_class}
                        )
                        relationships.append(relationship)
    
    def _extract_javascript_module_level_entities(self, node: Node, code: str, code_lines: List[str], file_path: str, chunks: List[CodeChunk]) -> None:
        """Extract module-level variables and exports."""
        def find_declarations(n: Node) -> None:
            if n.type in ['variable_declaration', 'lexical_declaration']:
                start_line = n.start_point[0]
                end_line = n.end_point[0]
                
                # Extract variable names
                for child in n.children:
                    if child.type == 'variable_declarator':
                        for declarator_child in child.children:
                            if declarator_child.type == 'identifier':
                                var_name = self._get_node_text(declarator_child, code)
                                content = '\n'.join(code_lines[start_line:end_line + 1])
                                
                                chunk_id = self._generate_chunk_id(file_path, f"var:{var_name}", start_line)
                                
                                chunk = CodeChunk(
                                    id=chunk_id,
                                    content=content,
                                    language=SupportedLanguage.JAVASCRIPT,
                                    chunk_type="variable",
                                    name=var_name,
                                    start_line=start_line,
                                    end_line=end_line,
                                    start_byte=n.start_byte,
                                    end_byte=n.end_byte
                                )
                                chunks.append(chunk)
                                break
            
            for child in n.children:
                find_declarations(child)
        
        find_declarations(node)
    
    def _parse_generic(self, code: str, tree: Tree, file_path: str, language: SupportedLanguage) -> Tuple[List[CodeChunk], List[RelationshipInfo]]:
        """Generic parser for languages without specific implementations."""
        chunks = []
        relationships = []
        code_lines = code.split('\n')
        
        def traverse_node(node: Node, parent_id: Optional[str] = None) -> None:
            # Define function-like nodes for different languages
            function_types = {
                'function_declaration', 'function_definition', 'method_declaration',
                'function_item', 'impl_item', 'trait_item',  # Rust
                'function_declaration', 'method_declaration',  # Go, Java
                'function_definition', 'method_definition'  # C++
            }
            
            class_types = {
                'class_declaration', 'class_definition',
                'struct_item', 'enum_item',  # Rust
                'type_declaration', 'interface_declaration',  # Go
                'class_declaration', 'interface_declaration'  # Java
            }
            
            if node.type in function_types or node.type in class_types:
                chunk = self._create_generic_chunk(node, code, code_lines, file_path, parent_id, language)
                chunks.append(chunk)
                
                # Recurse with current chunk as parent
                for child in node.children:
                    traverse_node(child, chunk.id)
            else:
                # Continue traversing
                for child in node.children:
                    traverse_node(child, parent_id)
        
        traverse_node(tree.root_node)
        
        return chunks, relationships
    
    def _create_generic_chunk(self, node: Node, code: str, code_lines: List[str], file_path: str, parent_id: Optional[str], language: SupportedLanguage) -> CodeChunk:
        """Create a generic code chunk for any language."""
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        
        # Try to extract name from common patterns
        name = None
        for child in node.children:
            if child.type in ['identifier', 'field_identifier', 'type_identifier']:
                name = self._get_node_text(child, code)
                break
        
        content = '\n'.join(code_lines[start_line:end_line + 1])
        chunk_id = self._generate_chunk_id(file_path, name or node.type, start_line)
        
        # Calculate complexity
        complexity = self._calculate_complexity(content)
        
        return CodeChunk(
            id=chunk_id,
            content=content,
            language=language,
            chunk_type=node.type,
            name=name,
            start_line=start_line,
            end_line=end_line,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            parent_id=parent_id,
            complexity_score=complexity
        )
    
    # Helper methods
    
    def _get_node_text(self, node: Node, code: str) -> str:
        """Extract text content from a Tree-sitter node."""
        return code[node.start_byte:node.end_byte]
    
    def _generate_chunk_id(self, file_path: str, name: str, start_line: int) -> str:
        """Generate a unique ID for a code chunk."""
        content = f"{file_path}:{name}:{start_line}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _extract_python_docstring(self, node: Node, code: str) -> Optional[str]:
        """Extract docstring from Python function or class."""
        for child in node.children:
            if child.type == 'block':
                for block_child in child.children:
                    if block_child.type == 'expression_statement':
                        for expr_child in block_child.children:
                            if expr_child.type == 'string':
                                return self._get_node_text(expr_child, code).strip('"\'')
        return None
    
    def _extract_python_annotations(self, node: Node, code: str) -> Dict[str, Any]:
        """Extract Python decorators and type annotations."""
        annotations = {}
        
        # Extract decorators
        decorators = []
        for child in node.children:
            if child.type == 'decorator':
                decorators.append(self._get_node_text(child, code))
        
        if decorators:
            annotations['decorators'] = decorators
        
        # Extract type annotations
        if node.type == 'function_definition':
            for child in node.children:
                if child.type == 'parameters':
                    # Extract parameter types
                    param_types = {}
                    for param in child.children:
                        if param.type == 'typed_parameter':
                            param_name = None
                            param_type = None
                            for param_child in param.children:
                                if param_child.type == 'identifier':
                                    param_name = self._get_node_text(param_child, code)
                                elif param_child.type == 'type':
                                    param_type = self._get_node_text(param_child, code)
                            
                            if param_name and param_type:
                                param_types[param_name] = param_type
                    
                    if param_types:
                        annotations['parameter_types'] = param_types
        
        return annotations
    
    def _extract_python_imports(self, node: Node, code: str) -> List[str]:
        """Extract imported modules from Python import statements."""
        imports = []
        
        if node.type == 'import_statement':
            for child in node.children:
                if child.type == 'dotted_as_names':
                    for name_child in child.children:
                        if name_child.type == 'dotted_as_name':
                            for dotted_child in name_child.children:
                                if dotted_child.type == 'dotted_name':
                                    imports.append(self._get_node_text(dotted_child, code))
        
        elif node.type == 'import_from_statement':
            for child in node.children:
                if child.type == 'dotted_name':
                    imports.append(self._get_node_text(child, code))
        
        return imports
    
    def _extract_javascript_jsdoc(self, node: Node, code: str) -> Optional[str]:
        """Extract JSDoc comments from JavaScript functions."""
        # JSDoc extraction would require parsing comments
        # This is a simplified implementation
        return None
    
    def _extract_javascript_imports(self, node: Node, code: str) -> List[str]:
        """Extract imported modules from JavaScript import statements."""
        imports = []
        
        for child in node.children:
            if child.type == 'string':
                # Extract module path from import statement
                module_path = self._get_node_text(child, code).strip('"\'')
                imports.append(module_path)
        
        return imports
    
    def _calculate_complexity(self, content: str) -> float:
        """Calculate cyclomatic complexity of code."""
        # Simplified complexity calculation
        # Count decision points
        decision_keywords = ['if', 'elif', 'else', 'while', 'for', 'try', 'except', 'finally', 'with', 'switch', 'case']
        
        complexity = 1.0  # Base complexity
        
        for keyword in decision_keywords:
            complexity += content.count(keyword)
        
        # Normalize by content length
        return complexity / max(len(content.split('\n')), 1)
    
    def detect_language(self, file_path: str, content: str = "") -> Optional[SupportedLanguage]:
        """Detect programming language from file extension or content."""
        file_extensions = {
            '.py': SupportedLanguage.PYTHON,
            '.js': SupportedLanguage.JAVASCRIPT,
            '.jsx': SupportedLanguage.JAVASCRIPT,
            '.ts': SupportedLanguage.TYPESCRIPT,
            '.tsx': SupportedLanguage.TYPESCRIPT,
            '.rs': SupportedLanguage.RUST,
            '.go': SupportedLanguage.GO,
            '.java': SupportedLanguage.JAVA,
            '.cpp': SupportedLanguage.CPP,
            '.cc': SupportedLanguage.CPP,
            '.cxx': SupportedLanguage.CPP,
            '.c': SupportedLanguage.CPP,
            '.h': SupportedLanguage.CPP,
            '.hpp': SupportedLanguage.CPP,
            '.cs': SupportedLanguage.C_SHARP,
            '.rb': SupportedLanguage.RUBY,
            '.php': SupportedLanguage.PHP,
            '.kt': SupportedLanguage.KOTLIN,
            '.swift': SupportedLanguage.SWIFT,
            '.jsp': SupportedLanguage.JSP,
            '.tag': SupportedLanguage.JSP,
            '.tagx': SupportedLanguage.JSP,
            '.xml': SupportedLanguage.XML,
            '.idl': SupportedLanguage.XML,  # CORBA IDL files
        }
        
        # Check file extension
        for ext, lang in file_extensions.items():
            if file_path.endswith(ext):
                return lang
        
        # Content-based detection (basic patterns)
        if content:
            if 'def ' in content and 'import ' in content:
                return SupportedLanguage.PYTHON
            elif 'function ' in content and ('var ' in content or 'let ' in content or 'const ' in content):
                return SupportedLanguage.JAVASCRIPT
            elif 'fn ' in content and 'use ' in content:
                return SupportedLanguage.RUST
            elif 'func ' in content and 'package ' in content:
                return SupportedLanguage.GO
            elif 'public class ' in content and 'import ' in content:
                return SupportedLanguage.JAVA
        
        return None
    
    def get_supported_languages(self) -> List[SupportedLanguage]:
        """Get list of supported languages."""
        return list(self.parsers.keys())
    
    def _parse_jsp(self, code: str, tree: Tree, file_path: str) -> Tuple[List[CodeChunk], List[RelationshipInfo]]:
        """Parse JSP files for business logic and Struts patterns."""
        chunks = []
        relationships = []
        code_lines = code.split('\n')
        
        # Extract JSP scriptlets (Java code embedded in JSP)
        scriptlet_pattern = re.compile(r'<%\s*(.*?)\s*%>', re.DOTALL)
        scriptlets = scriptlet_pattern.findall(code)
        
        for i, scriptlet in enumerate(scriptlets):
            if scriptlet.strip():
                chunk_id = f"{file_path}:scriptlet:{i}"
                
                # Analyze business logic in scriptlet
                business_rules = self._extract_business_rules_from_java(scriptlet)
                struts_patterns = self._extract_struts_patterns(scriptlet)
                
                chunk = CodeChunk(
                    id=chunk_id,
                    content=scriptlet,
                    language=SupportedLanguage.JSP,
                    chunk_type="scriptlet",
                    name=f"scriptlet_{i}",
                    start_line=self._find_line_number(code, scriptlet),
                    end_line=self._find_line_number(code, scriptlet) + scriptlet.count('\n'),
                    start_byte=0,
                    end_byte=len(scriptlet),
                    business_rules=business_rules,
                    framework_patterns=struts_patterns,
                    migration_notes=self._generate_jsp_migration_notes(scriptlet)
                )
                chunks.append(chunk)
        
        # Extract JSP directives and tags
        directive_pattern = re.compile(r'<%@\s*(.*?)\s*%>', re.DOTALL)
        directives = directive_pattern.findall(code)
        
        for i, directive in enumerate(directives):
            chunk_id = f"{file_path}:directive:{i}"
            chunk = CodeChunk(
                id=chunk_id,
                content=directive,
                language=SupportedLanguage.JSP,
                chunk_type="directive",
                name=f"directive_{i}",
                start_line=self._find_line_number(code, directive),
                end_line=self._find_line_number(code, directive),
                start_byte=0,
                end_byte=len(directive)
            )
            chunks.append(chunk)
        
        # Extract Struts tags and forms
        struts_tag_pattern = re.compile(r'<(html|bean|logic|nested):(\w+)([^>]*)>', re.IGNORECASE)
        struts_tags = struts_tag_pattern.findall(code)
        
        for i, (namespace, tag, attributes) in enumerate(struts_tags):
            chunk_id = f"{file_path}:struts_tag:{namespace}:{tag}:{i}"
            
            # Extract business significance
            business_purpose = self._infer_business_purpose_from_struts_tag(namespace, tag, attributes)
            
            chunk = CodeChunk(
                id=chunk_id,
                content=f"<{namespace}:{tag}{attributes}>",
                language=SupportedLanguage.JSP,
                chunk_type="struts_tag",
                name=f"{namespace}_{tag}",
                start_line=self._find_line_number(code, f"<{namespace}:{tag}"),
                end_line=self._find_line_number(code, f"<{namespace}:{tag}"),
                start_byte=0,
                end_byte=len(f"<{namespace}:{tag}{attributes}>"),
                framework_patterns={"struts_namespace": namespace, "tag_type": tag, "business_purpose": business_purpose},
                migration_notes=[f"Struts {namespace}:{tag} -> Angular component/directive"]
            )
            chunks.append(chunk)
        
        return chunks, relationships
    
    def _parse_xml(self, code: str, tree: Tree, file_path: str) -> Tuple[List[CodeChunk], List[RelationshipInfo]]:
        """Parse XML files for configuration and CORBA IDL."""
        chunks = []
        relationships = []
        
        # Handle CORBA IDL files
        if file_path.endswith('.idl'):
            return self._parse_corba_idl(code, file_path)
        
        # Handle Struts configuration
        if 'struts-config' in code or 'action-mappings' in code:
            return self._parse_struts_config(code, file_path)
        
        # Generic XML parsing for configuration
        return self._parse_generic_xml(code, file_path)
    
    def _parse_corba_idl(self, code: str, file_path: str) -> Tuple[List[CodeChunk], List[RelationshipInfo]]:
        """Parse CORBA IDL files for service interfaces."""
        chunks = []
        relationships = []
        
        # Extract interface definitions
        interface_pattern = re.compile(r'interface\s+(\w+)\s*(?::\s*([^{]+))?\s*{([^}]+)}', re.DOTALL)
        interfaces = interface_pattern.findall(code)
        
        for interface_name, inheritance, interface_body in interfaces:
            chunk_id = f"{file_path}:interface:{interface_name}"
            
            # Extract methods from interface
            method_pattern = re.compile(r'(\w+)\s+(\w+)\s*\([^)]*\)', re.MULTILINE)
            methods = method_pattern.findall(interface_body)
            
            business_operations = []
            for return_type, method_name in methods:
                business_operations.append(f"{return_type} {method_name}")
            
            chunk = CodeChunk(
                id=chunk_id,
                content=f"interface {interface_name} {{{interface_body}}}",
                language=SupportedLanguage.XML,
                chunk_type="corba_interface",
                name=interface_name,
                start_line=self._find_line_number(code, f"interface {interface_name}"),
                end_line=self._find_line_number(code, f"interface {interface_name}") + interface_body.count('\n'),
                start_byte=0,
                end_byte=len(interface_body),
                framework_patterns={
                    "corba_interface": interface_name,
                    "inheritance": inheritance.strip() if inheritance else None,
                    "business_operations": business_operations
                },
                business_rules=[f"Service contract: {interface_name}"],
                migration_notes=[f"CORBA interface {interface_name} -> GraphQL service/resolver"]
            )
            chunks.append(chunk)
            
            # Create relationships for inheritance
            if inheritance:
                for parent in inheritance.split(','):
                    parent = parent.strip()
                    relationships.append(RelationshipInfo(
                        source_id=chunk_id,
                        target_id=f"{file_path}:interface:{parent}",
                        relationship_type="extends",
                        source_location=(chunk.start_line, 0)
                    ))
        
        return chunks, relationships
    
    def _parse_struts_config(self, code: str, file_path: str) -> Tuple[List[CodeChunk], List[RelationshipInfo]]:
        """Parse Struts configuration XML for action mappings."""
        chunks = []
        relationships = []
        
        # Extract action mappings
        action_pattern = re.compile(r'<action\s+([^>]+)>', re.IGNORECASE)
        actions = action_pattern.findall(code)
        
        for i, action_attrs in enumerate(actions):
            # Parse action attributes
            path_match = re.search(r'path\s*=\s*["\']([^"\']+)["\']', action_attrs)
            type_match = re.search(r'type\s*=\s*["\']([^"\']+)["\']', action_attrs)
            
            path = path_match.group(1) if path_match else f"action_{i}"
            action_class = type_match.group(1) if type_match else None
            
            chunk_id = f"{file_path}:action:{path}"
            
            chunk = CodeChunk(
                id=chunk_id,
                content=f"<action {action_attrs}>",
                language=SupportedLanguage.XML,
                chunk_type="struts_action_mapping",
                name=path,
                start_line=self._find_line_number(code, action_attrs),
                end_line=self._find_line_number(code, action_attrs),
                start_byte=0,
                end_byte=len(action_attrs),
                framework_patterns={
                    "struts_path": path,
                    "action_class": action_class,
                    "url_pattern": path
                },
                business_rules=[f"URL mapping: {path} -> business operation"],
                migration_notes=[f"Struts action {path} -> GraphQL mutation/query + Angular route"]
            )
            chunks.append(chunk)
            
            # Create relationship to Java action class
            if action_class:
                relationships.append(RelationshipInfo(
                    source_id=chunk_id,
                    target_id=f"java_class:{action_class}",
                    relationship_type="maps_to",
                    source_location=(chunk.start_line, 0)
                ))
        
        return chunks, relationships
    
    def _extract_business_rules_from_java(self, java_code: str) -> List[str]:
        """Extract business rules from Java code snippets."""
        business_rules = []
        
        # Look for validation patterns
        validation_patterns = [
            r'if\s*\(\s*([^)]+\.(?:isEmpty|isBlank|isNull))[^)]*\)',
            r'if\s*\(\s*([^)]+\s*[<>=!]+\s*[^)]+)\)',
            r'validate\w*\([^)]*\)',
            r'assert\w*\([^)]*\)'
        ]
        
        for pattern in validation_patterns:
            matches = re.findall(pattern, java_code, re.IGNORECASE)
            for match in matches:
                business_rules.append(f"Validation: {match}")
        
        return business_rules
    
    def _extract_struts_patterns(self, code: str) -> Dict[str, Any]:
        """Extract Struts-specific patterns from code."""
        patterns = {}
        
        # Look for ActionForm usage
        if 'ActionForm' in code:
            patterns['uses_action_form'] = True
        
        # Look for forward declarations
        forward_pattern = re.compile(r'mapping\.findForward\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
        forwards = forward_pattern.findall(code)
        if forwards:
            patterns['forwards'] = forwards
        
        # Look for business method calls
        business_method_pattern = re.compile(r'(\w+Service|\w+Manager|\w+DAO)\.(\w+)\s*\(', re.IGNORECASE)
        business_calls = business_method_pattern.findall(code)
        if business_calls:
            patterns['business_service_calls'] = [f"{service}.{method}" for service, method in business_calls]
        
        return patterns
    
    def _generate_jsp_migration_notes(self, scriptlet: str) -> List[str]:
        """Generate migration notes for JSP scriptlets."""
        notes = []
        
        if 'session.getAttribute' in scriptlet:
            notes.append("Session usage -> Angular state management (NgRx/services)")
        
        if 'request.getParameter' in scriptlet:
            notes.append("Request parameters -> Angular reactive forms")
        
        if any(db_pattern in scriptlet for db_pattern in ['Connection', 'PreparedStatement', 'ResultSet']):
            notes.append("Direct DB access -> GraphQL resolver with proper data layer")
        
        if 'out.println' in scriptlet:
            notes.append("Dynamic content generation -> Angular templating")
        
        return notes
    
    def _infer_business_purpose_from_struts_tag(self, namespace: str, tag: str, attributes: str) -> str:
        """Infer business purpose from Struts tag usage."""
        business_purposes = {
            'html:form': 'User input form',
            'html:text': 'Text input field',
            'html:select': 'Selection/dropdown',
            'html:submit': 'Form submission',
            'bean:write': 'Data display',
            'logic:iterate': 'List/collection display',
            'logic:present': 'Conditional display',
            'logic:notPresent': 'Conditional display'
        }
        
        tag_key = f"{namespace}:{tag}"
        return business_purposes.get(tag_key, f"UI component: {tag}")
    
    def _parse_generic_xml(self, code: str, file_path: str) -> Tuple[List[CodeChunk], List[RelationshipInfo]]:
        """Generic XML parsing for configuration files."""
        chunks = []
        relationships = []
        
        # Extract major XML elements that might represent configuration
        element_pattern = re.compile(r'<(\w+)([^>]*)>([^<]*)</\1>', re.DOTALL)
        elements = element_pattern.findall(code)
        
        for i, (tag_name, attributes, content) in enumerate(elements):
            if content.strip():
                chunk_id = f"{file_path}:config:{tag_name}:{i}"
                
                chunk = CodeChunk(
                    id=chunk_id,
                    content=f"<{tag_name}{attributes}>{content}</{tag_name}>",
                    language=SupportedLanguage.XML,
                    chunk_type="configuration",
                    name=tag_name,
                    start_line=self._find_line_number(code, f"<{tag_name}"),
                    end_line=self._find_line_number(code, f"</{tag_name}>"),
                    start_byte=0,
                    end_byte=len(content),
                    framework_patterns={"xml_element": tag_name, "config_type": "generic"}
                )
                chunks.append(chunk)
        
        return chunks, relationships
    
    def _find_line_number(self, full_text: str, search_text: str) -> int:
        """Find line number of text in full document."""
        try:
            index = full_text.find(search_text)
            if index == -1:
                return 1
            return full_text[:index].count('\n') + 1
        except:
            return 1
import logging
import time
import hashlib
from pydantic import BaseModel
from dataclasses import dataclass, field
from functools import cached_property, wraps
from typing import Any, Optional, Dict, List, Callable, ParamSpec, TypeVar
from infant.tools.web_browser.util import time_execution_sync

R = TypeVar('R')
P = ParamSpec('P')

@dataclass
class HashedDomElement:
	"""
	Hash of the dom element to be used as a unique identifier
	"""

	branch_path_hash: str
	attributes_hash: str
	xpath_hash: str
	# text_hash: str


class Coordinates(BaseModel):
	x: int
	y: int


class CoordinateSet(BaseModel):
	top_left: Coordinates
	top_right: Coordinates
	bottom_left: Coordinates
	bottom_right: Coordinates
	center: Coordinates
	width: int
	height: int
 

class ViewportInfo(BaseModel):
	scroll_x: int
	scroll_y: int
	width: int
	height: int
 
@dataclass(frozen=False)
class DOMBaseNode:
	is_visible: bool
	# Use None as default and set parent later to avoid circular reference issues
	parent: Optional['DOMElementNode']


@dataclass(frozen=False)
class DOMElementNode(DOMBaseNode):
	"""
	xpath: the xpath of the element from the last root node (shadow root or iframe OR document if no shadow root or iframe).
	To properly reference the element we need to recursively switch the root node until we find the element (work you way up the tree with `.parent`)
	"""

	tag_name: str
	xpath: str
	attributes: Dict[str, str]
	children: List[DOMBaseNode]
	is_interactive: bool = False
	is_top_element: bool = False
	is_in_viewport: bool = False
	shadow_root: bool = False
	highlight_index: Optional[int] = None
	viewport_coordinates: Optional[CoordinateSet] = None
	page_coordinates: Optional[CoordinateSet] = None
	viewport_info: Optional[ViewportInfo] = None

	def __repr__(self) -> str:
		tag_str = f'<{self.tag_name}'

		# Add attributes
		for key, value in self.attributes.items():
			tag_str += f' {key}="{value}"'
		tag_str += '>'

		# Add extra info
		extras = []
		if self.is_interactive:
			extras.append('interactive')
		if self.is_top_element:
			extras.append('top')
		if self.shadow_root:
			extras.append('shadow-root')
		if self.highlight_index is not None:
			extras.append(f'highlight:{self.highlight_index}')
		if self.is_in_viewport:
			extras.append('in-viewport')

		if extras:
			tag_str += f' [{", ".join(extras)}]'

		return tag_str

	@cached_property
	def hash(self) -> HashedDomElement:

		return HistoryTreeProcessor._hash_dom_element(self)

	def get_all_text_till_next_clickable_element(self, max_depth: int = -1) -> str:
		text_parts = []

		def collect_text(node: DOMBaseNode, current_depth: int) -> None:
			if max_depth != -1 and current_depth > max_depth:
				return

			# Skip this branch if we hit a highlighted element (except for the current node)
			if isinstance(node, DOMElementNode) and node != self and node.highlight_index is not None:
				return

			if isinstance(node, DOMTextNode):
				text_parts.append(node.text)
			elif isinstance(node, DOMElementNode):
				for child in node.children:
					collect_text(child, current_depth + 1)

		collect_text(self, 0)
		return '\n'.join(text_parts).strip()

	@time_execution_sync('--clickable_elements_to_string')
	def clickable_elements_to_string(self, include_attributes: list[str] | None = None) -> str:
		"""Convert the processed DOM content to HTML."""
		formatted_text = []

		def process_node(node: DOMBaseNode, depth: int) -> None:
			if isinstance(node, DOMElementNode):
				# Add element with highlight_index
				if node.highlight_index is not None:
					attributes_str = ''
					text = node.get_all_text_till_next_clickable_element()
					if include_attributes:
						attributes = list(
							set(
								[
									str(value)
									for key, value in node.attributes.items()
									if key in include_attributes and value != node.tag_name
								]
							)
						)
						if text in attributes:
							attributes.remove(text)
						attributes_str = ';'.join(attributes)
					line = f'[{node.highlight_index}]<{node.tag_name} '
					if attributes_str:
						line += f'{attributes_str}'
					if text:
						if attributes_str:
							line += f'>{text}'
						else:
							line += f'{text}'
					line += '/>'
					formatted_text.append(line)

				# Process children regardless
				for child in node.children:
					process_node(child, depth + 1)

			elif isinstance(node, DOMTextNode):
				# Add text only if it doesn't have a highlighted parent
				if not node.has_parent_with_highlight_index() and node.is_visible:  # and node.is_parent_top_element()
					formatted_text.append(f'{node.text}')

		process_node(self, 0)
		return '\n'.join(formatted_text)

	def get_file_upload_element(self, check_siblings: bool = True) -> Optional['DOMElementNode']:
		# Check if current element is a file input
		if self.tag_name == 'input' and self.attributes.get('type') == 'file':
			return self

		# Check children
		for child in self.children:
			if isinstance(child, DOMElementNode):
				result = child.get_file_upload_element(check_siblings=False)
				if result:
					return result

		# Check siblings only for the initial call
		if check_siblings and self.parent:
			for sibling in self.parent.children:
				if sibling is not self and isinstance(sibling, DOMElementNode):
					result = sibling.get_file_upload_element(check_siblings=False)
					if result:
						return result

		return None

@dataclass
class DOMHistoryElement:
	tag_name: str
	xpath: str
	highlight_index: Optional[int]
	entire_parent_branch_path: list[str]
	attributes: dict[str, str]
	shadow_root: bool = False
	css_selector: Optional[str] = None
	page_coordinates: Optional[CoordinateSet] = None
	viewport_coordinates: Optional[CoordinateSet] = None
	viewport_info: Optional[ViewportInfo] = None

	def to_dict(self) -> dict:
		page_coordinates = self.page_coordinates.model_dump() if self.page_coordinates else None
		viewport_coordinates = self.viewport_coordinates.model_dump() if self.viewport_coordinates else None
		viewport_info = self.viewport_info.model_dump() if self.viewport_info else None

		return {
			'tag_name': self.tag_name,
			'xpath': self.xpath,
			'highlight_index': self.highlight_index,
			'entire_parent_branch_path': self.entire_parent_branch_path,
			'attributes': self.attributes,
			'shadow_root': self.shadow_root,
			'css_selector': self.css_selector,
			'page_coordinates': page_coordinates,
			'viewport_coordinates': viewport_coordinates,
			'viewport_info': viewport_info,
		}

SelectorMap = dict[int, DOMElementNode]

class HistoryTreeProcessor:
	""" "
	Operations on the DOM elements

	@dev be careful - text nodes can change even if elements stay the same
	"""

	@staticmethod
	def convert_dom_element_to_history_element(dom_element: DOMElementNode) -> DOMHistoryElement:
		from infant.tools.web_browser.context import BrowserContext

		parent_branch_path = HistoryTreeProcessor._get_parent_branch_path(dom_element)
		css_selector = BrowserContext._enhanced_css_selector_for_element(dom_element)
		return DOMHistoryElement(
			dom_element.tag_name,
			dom_element.xpath,
			dom_element.highlight_index,
			parent_branch_path,
			dom_element.attributes,
			dom_element.shadow_root,
			css_selector=css_selector,
			page_coordinates=dom_element.page_coordinates,
			viewport_coordinates=dom_element.viewport_coordinates,
			viewport_info=dom_element.viewport_info,
		)

	@staticmethod
	def find_history_element_in_tree(dom_history_element: DOMHistoryElement, tree: DOMElementNode) -> Optional[DOMElementNode]:
		hashed_dom_history_element = HistoryTreeProcessor._hash_dom_history_element(dom_history_element)

		def process_node(node: DOMElementNode):
			if node.highlight_index is not None:
				hashed_node = HistoryTreeProcessor._hash_dom_element(node)
				if hashed_node == hashed_dom_history_element:
					return node
			for child in node.children:
				if isinstance(child, DOMElementNode):
					result = process_node(child)
					if result is not None:
						return result
			return None

		return process_node(tree)

	@staticmethod
	def compare_history_element_and_dom_element(dom_history_element: DOMHistoryElement, dom_element: DOMElementNode) -> bool:
		hashed_dom_history_element = HistoryTreeProcessor._hash_dom_history_element(dom_history_element)
		hashed_dom_element = HistoryTreeProcessor._hash_dom_element(dom_element)

		return hashed_dom_history_element == hashed_dom_element

	@staticmethod
	def _hash_dom_history_element(dom_history_element: DOMHistoryElement) -> HashedDomElement:
		branch_path_hash = HistoryTreeProcessor._parent_branch_path_hash(dom_history_element.entire_parent_branch_path)
		attributes_hash = HistoryTreeProcessor._attributes_hash(dom_history_element.attributes)
		xpath_hash = HistoryTreeProcessor._xpath_hash(dom_history_element.xpath)

		return HashedDomElement(branch_path_hash, attributes_hash, xpath_hash)

	@staticmethod
	def _hash_dom_element(dom_element: DOMElementNode) -> HashedDomElement:
		parent_branch_path = HistoryTreeProcessor._get_parent_branch_path(dom_element)
		branch_path_hash = HistoryTreeProcessor._parent_branch_path_hash(parent_branch_path)
		attributes_hash = HistoryTreeProcessor._attributes_hash(dom_element.attributes)
		xpath_hash = HistoryTreeProcessor._xpath_hash(dom_element.xpath)
		# text_hash = DomTreeProcessor._text_hash(dom_element)

		return HashedDomElement(branch_path_hash, attributes_hash, xpath_hash)

	@staticmethod
	def _get_parent_branch_path(dom_element: DOMElementNode) -> list[str]:
		parents: list[DOMElementNode] = []
		current_element: DOMElementNode = dom_element
		while current_element.parent is not None:
			parents.append(current_element)
			current_element = current_element.parent

		parents.reverse()

		return [parent.tag_name for parent in parents]

	@staticmethod
	def _parent_branch_path_hash(parent_branch_path: list[str]) -> str:
		parent_branch_path_string = '/'.join(parent_branch_path)
		return hashlib.sha256(parent_branch_path_string.encode()).hexdigest()

	@staticmethod
	def _attributes_hash(attributes: dict[str, str]) -> str:
		attributes_string = ''.join(f'{key}={value}' for key, value in attributes.items())
		return hashlib.sha256(attributes_string.encode()).hexdigest()

	@staticmethod
	def _xpath_hash(xpath: str) -> str:
		return hashlib.sha256(xpath.encode()).hexdigest()

	@staticmethod
	def _text_hash(dom_element: DOMElementNode) -> str:
		""" """
		text_string = dom_element.get_all_text_till_next_clickable_element()
		return hashlib.sha256(text_string.encode()).hexdigest()

@dataclass(frozen=False)
class DOMBaseNode:
	is_visible: bool
	# Use None as default and set parent later to avoid circular reference issues
	parent: Optional['DOMElementNode']


@dataclass(frozen=False)
class DOMTextNode(DOMBaseNode):
	text: str
	type: str = 'TEXT_NODE'

	def has_parent_with_highlight_index(self) -> bool:
		current = self.parent
		while current is not None:
			# stop if the element has a highlight index (will be handled separately)
			if current.highlight_index is not None:
				return True

			current = current.parent
		return False

	def is_parent_in_viewport(self) -> bool:
		if self.parent is None:
			return False
		return self.parent.is_in_viewport

	def is_parent_top_element(self) -> bool:
		if self.parent is None:
			return False
		return self.parent.is_top_element



@dataclass
class DOMState:
	element_tree: DOMElementNode
	selector_map: SelectorMap
# Pydantic
class TabInfo(BaseModel):
	"""Represents information about a browser tab"""

	page_id: int
	url: str
	title: str


@dataclass
class BrowserState(DOMState):
	url: str
	title: str
	tabs: list[TabInfo]
	screenshot: Optional[str] = None
	pixels_above: int = 0
	pixels_below: int = 0
	browser_errors: list[str] = field(default_factory=list)


@dataclass
class BrowserStateHistory:
	url: str
	title: str
	tabs: list[TabInfo]
	interacted_element: list[DOMHistoryElement | None] | list[None]
	screenshot: Optional[str] = None

	def to_dict(self) -> dict[str, Any]:
		data = {}
		data['tabs'] = [tab.model_dump() for tab in self.tabs]
		data['screenshot'] = self.screenshot
		data['interacted_element'] = [el.to_dict() if el else None for el in self.interacted_element]
		data['url'] = self.url
		data['title'] = self.title
		return data


class BrowserError(Exception):
	"""Base class for all browser errors"""


class URLNotAllowedError(BrowserError):
	"""Error raised when a URL is not allowed"""
"""Text redaction engine implementing overlap-safe reverse replacement and stable typed tokens."""

from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from .models import Finding, Block


class TextRedactor:
    """
    Safely redacts PII spans from document blocks or raw text.
    
    Guarantees:
    - Overlap resolution: Resolves overlapping or conflicting spans deterministically.
    - Reverse replacement: Substitutes spans in descending start-offset order to preserve index validity.
    - Stable placeholders: Re-uses the same token (e.g., [PERSON_1]) for recurring identical entities within a document.
    - Structure preservation: Retains newlines, tables, punctuation, and preceding/succeeding context intact.
    """

    def __init__(self, token_format: str = "[{entity_type}_{index}]"):
        self.token_format = token_format

    def resolve_overlaps(self, findings: List[Finding]) -> List[Finding]:
        """
        Resolves overlapping findings deterministically.
        Sorts primarily by start offset ascending, and resolves collisions by picking the longer span
        or higher confidence finding.
        """
        if not findings:
            return []

        # Sort by start ascending, then length descending, then confidence descending
        sorted_findings = sorted(
            findings,
            key=lambda f: (f.start, -(f.end - f.start), -f.confidence)
        )

        resolved: List[Finding] = []
        for current in sorted_findings:
            if not resolved:
                resolved.append(current)
                continue

            last = resolved[-1]
            # Check overlap within the same block
            if current.block_id == last.block_id and current.start < last.end:
                # Collision: last one is already longer or higher confidence due to sort key
                continue
            else:
                resolved.append(current)

        return resolved

    def redact_block(
        self,
        block: Block,
        findings: List[Finding],
        token_registry: Dict[str, Dict[str, str]],
        entity_counters: Dict[str, int]
    ) -> Tuple[str, List[Finding]]:
        """
        Redacts a single Block using descending start offsets.
        
        Args:
            block: The source Block containing text.
            findings: List of Finding items belonging to this block.
            token_registry: Nested dict mapping entity_type -> {entity_value: token}
            entity_counters: Dict mapping entity_type -> count of unique entities assigned so far
            
        Returns:
            Tuple of (sanitized_block_text, applied_findings)
        """
        block_findings = [f for f in findings if f.block_id == block.block_id]
        if not block_findings:
            return block.text, []

        resolved = self.resolve_overlaps(block_findings)
        # Sort in descending order of start offset so replacements don't shift upcoming offsets
        descending_findings = sorted(resolved, key=lambda f: f.start, reverse=True)

        text_chars = list(block.text)

        for finding in descending_findings:
            start, end = finding.start, finding.end
            if start < 0 or end > len(text_chars) or start >= end:
                continue

            original_val = "".join(text_chars[start:end])
            finding.original_text = original_val
            entity_type = finding.entity_type.upper()

            # Determine stable token
            norm_val = original_val.strip().lower()
            if norm_val not in token_registry[entity_type]:
                entity_counters[entity_type] += 1
                token_index = entity_counters[entity_type]
                token = self.token_format.format(entity_type=entity_type, index=token_index)
                token_registry[entity_type][norm_val] = token
            else:
                token = token_registry[entity_type][norm_val]

            # Replace span
            text_chars[start:end] = list(token)

        sanitized_text = "".join(text_chars)
        return sanitized_text, resolved

    def redact_document(
        self,
        blocks: List[Block],
        findings: List[Finding]
    ) -> Tuple[List[Block], Dict[str, str], Dict[str, int]]:
        """
        Redacts an entire document consisting of multiple blocks.
        
        Returns:
            Tuple of (sanitized_blocks, stable_token_mapping, category_counts)
        """
        token_registry: Dict[str, Dict[str, str]] = defaultdict(dict)
        entity_counters: Dict[str, int] = defaultdict(int)
        category_counts: Dict[str, int] = defaultdict(int)

        sanitized_blocks: List[Block] = []

        for block in blocks:
            sanitized_text, applied = self.redact_block(
                block, findings, token_registry, entity_counters
            )
            for f in applied:
                category_counts[f.entity_type] += 1

            new_block = Block(
                document_id=block.document_id,
                block_id=block.block_id,
                page_or_slide=block.page_or_slide,
                source_kind=block.source_kind,
                reading_order=block.reading_order,
                text=sanitized_text,
                table_row=block.table_row,
                table_column=block.table_column,
                bbox=block.bbox,
                OCR_confidence=block.OCR_confidence,
                extraction_complete=block.extraction_complete
            )
            sanitized_blocks.append(new_block)

        # Flatten registry for reference {original_val: token}
        flat_mapping = {}
        for entity_type, val_map in token_registry.items():
            for val, token in val_map.items():
                flat_mapping[val] = token

        return sanitized_blocks, flat_mapping, dict(category_counts)

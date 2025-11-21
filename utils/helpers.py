import re
from typing import List, Tuple

def flatten_value(val):
    """Flatten list/tuple values to semicolon-separated strings - original function"""
    if isinstance(val, (list, tuple)):
        return ";".join(str(x) for x in val)
    return "" if val is None else str(val)

def extract_numbers_from_slots(slots: List[str], pattern: str) -> List[int]:
    """Extract numbers from slot names matching pattern"""
    numbers = []
    for slot in slots:
        match = re.match(pattern, slot)
        if match:
            numbers.append(int(match.group(1)))
    return sorted(numbers)

def validate_sequence(numbers: List[int]) -> Tuple[bool, List[int]]:
    """Check if numbers form a complete sequence starting from 1"""
    if not numbers:
        return True, []
    
    expected = list(range(1, max(numbers) + 1))
    missing = [n for n in expected if n not in numbers]
    return len(missing) == 0, missing

def validate_mpu_sequence(slot_names: str) -> Tuple[bool, List[str]]:
    """Original MPU sequence validation logic"""
    slots = [s for s in slot_names.split(";") if s]
    
    # Extract MPU numbers
    mpu_numbers = sorted([
        int(match.group(1))
        for s in slots
        for match in [re.match(r"mpu(\d+)-m$", s)]
        if match
    ])
    
    missing_mpu = []
    if mpu_numbers:
        for n in range(1, max(mpu_numbers) + 1):
            if n not in mpu_numbers:
                missing_mpu.append(f"mpu{n}-m")
    
    return len(missing_mpu) == 0, missing_mpu

def validate_blog_sequence(slot_names: str) -> Tuple[bool, List[str]]:
    """Original blog sequence validation logic"""
    slots = [s for s in slot_names.split(";") if s]
    
    # Extract blog numbers
    blog_numbers = sorted([
        int(match.group(1))
        for s in slots
        for match in [re.match(r"blog(\d+)-m$", s)]
        if match
    ])
    
    missing_blog = []
    if blog_numbers:
        for n in range(1, max(blog_numbers) + 1):
            if n not in blog_numbers:
                missing_blog.append(f"blog{n}-m")
    
    return len(missing_blog) == 0, missing_blog
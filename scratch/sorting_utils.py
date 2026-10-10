"""
Sorting algorithms implementation in Python.
Provides a robust sorting function along with options for standard sorting,
custom key functions, and various common sorting algorithms (Merge Sort, Quick Sort, Timsort wrapper).
"""

from typing import List, Callable, TypeVar, Optional, Any

T = TypeVar('T')

def advanced_sort(
    items: List[T],
    *,
    reverse: bool = False,
    key: Optional[Callable[[T], Any]] = None,
    algorithm: str = "timsort"
) -> List[T]:
    """
    Sorts a list of items using the specified algorithm and parameters.

    Args:
        items: The list of items to sort.
        reverse: If True, sort in descending order.
        key: A function of one argument used to extract a comparison key from each element.
        algorithm: The sorting algorithm to use ('timsort', 'mergesort', 'quicksort').

    Returns:
        A new sorted list (does not mutate the original list).
    """
    if not items:
        return []

    # Make a copy to avoid mutating the original list
    arr = list(items)

    algo = algorithm.lower()
    if algo == "timsort":
        # Python's built-in sorted uses Timsort ($O(n \log n)$)
        return sorted(arr, reverse=reverse, key=key)
    elif algo == "mergesort":
        return _merge_sort(arr, reverse=reverse, key=key)
    elif algo == "quicksort":
        return _quick_sort(arr, reverse=reverse, key=key)
    else:
        raise ValueError(f"Unknown sorting algorithm: '{algorithm}'. Choose from 'timsort', 'mergesort', 'quicksort'.")


def _merge_sort(arr: List[T], reverse: bool = False, key: Optional[Callable[[T], Any]] = None) -> List[T]:
    """Implementation of Merge Sort (O(n log n) time, O(n) space)."""
    if len(arr) <= 1:
        return arr

    mid = len(arr) // 2
    left = _merge_sort(arr[:mid], reverse=reverse, key=key)
    right = _merge_sort(arr[mid:], reverse=reverse, key=key)

    return _merge(left, right, reverse=reverse, key=key)


def _merge(left: List[T], right: List[T], reverse: bool = False, key: Optional[Callable[[T], Any]] = None) -> List[T]:
    result = []
    i = j = 0

    while i < len(left) and j < len(right):
        val_i = key(left[i]) if key is not None else left[i]
        val_j = key(right[j]) if key is not None else right[j]

        # Condition for sorting order
        if reverse:
            condition = val_i >= val_j
        else:
            condition = val_i <= val_j

        if condition:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result


def _quick_sort(arr: List[T], reverse: bool = False, key: Optional[Callable[[T], Any]] = None) -> List[T]:
    """Implementation of Quick Sort (O(n log n) average time)."""
    if len(arr) <= 1:
        return arr

    pivot = arr[len(arr) // 2]
    pivot_val = key(pivot) if key is not None else pivot

    left = []
    middle = []
    right = []

    for item in arr:
        item_val = key(item) if key is not None else item
        if item_val == pivot_val:
            middle.append(item)
        elif (item_val < pivot_val and not reverse) or (item_val > pivot_val and reverse):
            left.append(item)
        else:
            right.append(item)

    return _quick_sort(left, reverse=reverse, key=key) + middle + _quick_sort(right, reverse=reverse, key=key)


if __name__ == "__main__":
    # Example usage and tests
    numbers = [31, -4, 15, 9, 26, 5, 35, 9, 7, 93]
    print("Original:", numbers)
    print("Timsort (Default):", advanced_sort(numbers))
    print("Timsort (Descending):", advanced_sort(numbers, reverse=True))
    print("Merge Sort:", advanced_sort(numbers, algorithm="mergesort"))
    print("Quick Sort:", advanced_sort(numbers, algorithm="quicksort"))

    # Sorting with custom key function (e.g., sorting by absolute value or string length)
    words = ["strawberry", "fig", "banana", "apple", "date"]
    print("\nWords:", words)
    print("Sorted by length:", advanced_sort(words, key=len))
    print("Sorted by length (descending):", advanced_sort(words, key=len, reverse=True))

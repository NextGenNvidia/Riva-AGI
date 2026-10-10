import unittest
from scratch.sorting_utils import advanced_sort

class TestSortingUtils(unittest.TestCase):

    def test_empty_and_single(self):
        self.assertEqual(advanced_sort([]), [])
        self.assertEqual(advanced_sort([42]), [42])

    def test_timsort(self):
        arr = [5, 2, 9, 1, 5, 6]
        self.assertEqual(advanced_sort(arr, algorithm="timsort"), [1, 2, 5, 5, 6, 9])
        self.assertEqual(advanced_sort(arr, algorithm="timsort", reverse=True), [9, 6, 5, 5, 2, 1])

    def test_mergesort(self):
        arr = [10, -1, 2, 5, 0, 8]
        self.assertEqual(advanced_sort(arr, algorithm="mergesort"), [-1, 0, 2, 5, 8, 10])
        self.assertEqual(advanced_sort(arr, algorithm="mergesort", reverse=True), [10, 8, 5, 2, 0, -1])

    def test_quicksort(self):
        arr = [3, 1, 4, 1, 5, 9, 2, 6]
        self.assertEqual(advanced_sort(arr, algorithm="quicksort"), [1, 1, 2, 3, 4, 5, 6, 9])
        self.assertEqual(advanced_sort(arr, algorithm="quicksort", reverse=True), [9, 6, 5, 4, 3, 2, 1, 1])

    def test_custom_key(self):
        words = ["apple", "pie", "banana", "kiwi"]
        # Sort by string length
        self.assertEqual(
            advanced_sort(words, key=len),
            ["pie", "kiwi", "apple", "banana"]
        )

    def test_invalid_algorithm(self):
        with self.assertRaises(ValueError):
            advanced_sort([1, 2, 3], algorithm="bogo")

if __name__ == "__main__":
    unittest.main()

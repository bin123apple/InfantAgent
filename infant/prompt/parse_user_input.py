parse_user_input_prompt = '''I would like your help in extracting the question and corresponding mandatory requirements from the user's request. 
For example, if the user raises a code-related question that includes unit tests, then the mandatory requirement would be the inclusion of unit tests. 
Similarly, if the user requests an article written in a specific style, the mandatory requirement would be that the final article conforms to that style.
If there is no mandatory requirement, please return None.
You should put the extracted mandatory requirements inside the <mandatory_standards>...</mandatory_standards> tag.
Here are some examples:
### User request ###:
Can you provide Python code to calculate the factorial of a number? Please include error handling for invalid input.
### Mandatory Requirement ###:
<mandatory_standards>
The code must include error handling for invalid input.
</mandatory_standards>

### User request ###:
Write a blog post on the benefits of AI in healthcare, using a formal, informative tone.
### Mandatory Requirement ###:
<mandatory_standards>
The article must be written in a formal, informative tone.
</mandatory_standards>

### User request ###:
Hello, nice to meet you!
### Mandatory Requirement ###:
<mandatory_standards>
None
</mandatory_standards>

### User request ###:
Implement a function two_sum(nums, target) that finds two numbers in a given list nums that add up to a target sum target. 
The following unit test should pass:
import unittest

class TestTwoSum(unittest.TestCase):
    def test_example_case(self):
        # Example test case
        self.assertEqual(two_sum([2, 7, 11, 15], 9), [0, 1])

    def test_no_solution(self):
        # Case with no solution
        self.assertIsNone(two_sum([1, 2, 3], 7))

if __name__ == "__main__":
    unittest.main()
### Mandatory Requirement ###:
<mandatory_standards>
The function two_sum must pass the provided unit tests:
import unittest

class TestTwoSum(unittest.TestCase):
    def test_example_case(self):
        # Example test case
        self.assertEqual(two_sum([2, 7, 11, 15], 9), [0, 1])

    def test_no_solution(self):
        # Case with no solution
        self.assertIsNone(two_sum([1, 2, 3], 7))

if __name__ == "__main__":
    unittest.main()
</mandatory_standards>

Here is the real user request:
### User request ###:
{user_request}
### Mandatory Requirement ###:
'''
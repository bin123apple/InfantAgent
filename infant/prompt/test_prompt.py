# Basic test for Agent step
basic_test = '''Share your thoughts on travel.
描述你最喜欢的一次经历。
Give your predictions for world development in the next ten years.
说说你对人工智能技术的态度。
Explain why you think education is important.
谈谈你最喜欢的电影或电视剧。
Describe your ideal career path or professional goals.
讨论你对健康饮食的看法。
Explain how you manage your time.
说说你希望去的梦想之地。
Talk about your perspective on holidays.
解释你对友情的理解和看法。
Describe your favorite hobby or interest.
分享你对家庭的重要性的看法。
Explain your stance on environmental protection.
说说你对未来职业发展的期望。
Describe how you define "success."
讨论你如何看待失败和挫折。
Explain how you manage stress.
描述你对未来的理想生活状态。
Describe how you keep in touch with friends and family.
分享你对冒险的态度。
Talk about your views on a particular form of art.
解释你最喜欢的书籍或作家的影响。
Describe what your ideal day would look like.
说说你对科技发展和社会变化的看法。
Discuss your attitude towards learning a new language.
讲讲你如何面对变化和新的挑战。
What is your favorite book and why?
如果你可以瞬间掌握一门新技能，你会选择什么？
What is your favorite holiday and why?
如果可以访问一个历史时期，你会选择哪个年代？
What is your favorite animal?
你认为未来100年内最大的科技突破会是什么？
If you could have dinner with any celebrity, who would it be?
你更喜欢早起还是熬夜？为什么？
What value do you find most important in life?
你如何放松和减压？
What is your favorite home-cooked meal?
你去过最令人惊叹的地方是哪里？
Would you choose space travel or deep-sea exploration?
如果你可以改变世界上的一件事，你会选择什么？
你喜欢独自旅行还是和朋友一起？
Would you prefer reading a physical book or listening to an audiobook?
如果你有一天可以隐身，你会做什么？
What are your thoughts on the future of AI and automation?
你最喜欢哪一部电影或电视剧？
What is your dream job?
你会尝试素食或完全素食的生活方式吗？
How do you deal with failure and setbacks?
你会选择一个农村生活还是一个城市生活？
Are you interested in investing and personal finance?
如果你可以住在任何一个国家，你会选择哪里？
What do you think should be changed in the education system?
你更喜欢冷天气还是热天气？
Do you think AI will replace certain jobs?
你是否有某种特别的收集爱好？
What is the most challenging experience you have faced and how did you overcome it?'''

code_test_cn = '''编写一个函数 unique_sorted_list(nums: List[int]) -> List[int]，它接收一个整数数组并返回去重和排序后的数组。你写的函数应确保以下单元测试通过：
输入 [3, 1, 2, 3, 2]，期望输出 [1, 2, 3]。
输入 []，期望输出 []。
输入 [5, 5, 5]，期望输出 [5]
'''

code_test_en = '''Write a function diagonal_sum(matrix: List[List[int]]) -> int that takes a square matrix and returns the sum of its main diagonal elements. Assume the input matrix is always square (i.e., same number of rows and columns). You should make sure that the following unit tests are passed:
Input [[1, 2, 3], [4, 5, 6], [7, 8, 9]], expected output 15 (1 + 5 + 9).
Input [[2]], expected output 2.
Input [[1, 0], [0, 3]], expected output 4.
'''

math_test_cn = '''证明对于所有正整数 $n$数列 $S_n = 1^3 + 2^3 + \ldots + n^3$
的和可以表示为公式：$S_n = \left( \\frac{n(n + 1)}{2} \\right)^2$, 给出完整的证明步骤。'''

math_test_en = '''Find the sum of the infinite geometric series given by $S = 5 + 2.5 + 1.25 + ...$
Determine the sum, showing your calculations.
'''

physics_test_cn = '''一个质量为 $m$ 的物体以速度 $v$ 撞击一个静止的质量为 $M$ 的物体，碰撞后两物体粘在一起，以速度 $V$ 运动。求碰撞后的速度 $V$。'''

physics_test_en = '''Prove that the work done $W$ by a constant force $F$ acting on an object that moves a displacement $d$ in the direction of the force is given by
$W = Fd$
Provide a detailed explanation based on the definition of work and vector operations.
'''

chemistry_test_cn = '''解释为什么氢气是一种极好的燃料。'''

chemistry_test_en = '''Explain why hydrogen gas is an excellent fuel source. Provide a detailed explanation of its properties and combustion process.'''

biology_test_cn = '''简述光合作用的基本过程，并说明光反应和暗反应之间的区别。'''

biology_test_en = '''Explain why cells are considered the basic unit of life. Provide a detailed explanation of their structure and function.'''

os_operation_test_en = '''Hey, my LibreOffice Writer seems to have frozen and I can't get it to close normally. Can you help me force quit the application from the command line? I'm on Ubuntu and I don't want to restart my computer or lose any other work I have open.'''
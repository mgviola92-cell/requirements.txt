"""Procedural two-choice puzzles with exact, computed answers."""
import random
import uuid

KINDS=("sum","difference","product","division","square","cube","percent",
       "average","remainder","arithmetic_series","geometric_series",
       "alternating_series","triangular","fibonacci","factorial",
       "gcd","lcm","fraction","ratio","linear_equation","area_rectangle",
       "perimeter_rectangle","area_triangle","volume_box","speed",
       "time","distance","discount","tax","simple_interest",
       "probability","combinations","binary","hexadecimal",
       "absolute","power","square_root","cube_root","prime",
       "even_odd","divisibility","missing_number","age_difference",
       "unit_conversion","angles","polygon_sides","mean_missing",
       "median","mode","sets_union","sets_intersection")

def _gcd(a,b):
    while b:a,b=b,a%b
    return a

def generate(level=1, mode="duo"):
    level=max(1,min(6,int(level)))
    a=random.randint(3,10+level*9)
    b=random.randint(2,7+level*4)
    c=random.randint(2,5+level*3)
    kind=random.choice(KINDS)
    if kind=="sum":q,v=f"{a} + {b} + {c} = ?",a+b+c
    elif kind=="difference":q,v=f"{a+b+c} - {b} - {c} = ?",a
    elif kind=="product":q,v=f"{a} x {b} = ?",a*b
    elif kind=="division":q,v=f"{a*b} / {b} = ?",a
    elif kind=="square":q,v=f"{a} squared = ?",a*a
    elif kind=="cube":q,v=f"{b} cubed = ?",b**3
    elif kind=="percent":q,v=f"25% of {a*4} = ?",a
    elif kind=="average":q,v=f"Average of {a}, {a+2*b} = ?",a+b
    elif kind=="remainder":q,v=f"Remainder of {a*b+c} divided by {b} = ?",c%b
    elif kind=="arithmetic_series":q,v=f"Next: {a}, {a+b}, {a+2*b}, ?",a+3*b
    elif kind=="geometric_series":q,v=f"Next: {a}, {a*2}, {a*4}, ?",a*8
    elif kind=="alternating_series":q,v=f"Next: {a}, {a+b}, {a+b-c}, {a+2*b-c}, ?",a+2*b-2*c
    elif kind=="triangular":q,v=f"1 + 2 + ... + {b} = ?",b*(b+1)//2
    elif kind=="fibonacci":q,v=f"Next: {a}, {b}, {a+b}, {a+2*b}, ?",2*a+3*b
    elif kind=="factorial":
        n=random.randint(3,6);q,v=f"{n}! = ?",__import__("math").factorial(n)
    elif kind=="gcd":q,v=f"GCD of {a*b} and {a*c} = ?",a*_gcd(b,c)
    elif kind=="lcm":q,v=f"LCM of {a} and {b} = ?",a*b//_gcd(a,b)
    elif kind=="fraction":q,v=f"One third of {a*3} = ?",a
    elif kind=="ratio":q,v=f"Ratio {a}:{b}. If first becomes {a*3}, second = ?",b*3
    elif kind=="linear_equation":q,v=f"Find x: {b}x + {c} = {b*a+c}. x = ?",a
    elif kind=="area_rectangle":q,v=f"Rectangle area: length {a}, width {b} = ?",a*b
    elif kind=="perimeter_rectangle":q,v=f"Rectangle perimeter: sides {a} and {b} = ?",2*(a+b)
    elif kind=="area_triangle":q,v=f"Triangle area: base {a*2}, height {b} = ?",a*b
    elif kind=="volume_box":q,v=f"Box volume: {a} x {b} x {c} = ?",a*b*c
    elif kind=="speed":q,v=f"Travel {a*b} km in {b} hours. Speed km/h = ?",a
    elif kind=="time":q,v=f"Travel {a*b} km at {a} km/h. Hours = ?",b
    elif kind=="distance":q,v=f"Speed {a} km/h for {b} hours. Distance = ?",a*b
    elif kind=="discount":q,v=f"25% off {a*4}. New price = ?",a*3
    elif kind=="tax":q,v=f"10% tax on {a*10}. Total = ?",a*11
    elif kind=="simple_interest":q,v=f"Simple interest: {a*100} at 5% for {b} years = ?",a*5*b
    elif kind=="probability":q,v=f"Bag: {a} red, {b} blue. How many balls in total? ",a+b
    elif kind=="combinations":q,v=f"Number of ways to choose 2 from {b} distinct items = ?",b*(b-1)//2
    elif kind=="binary":q,v=f"Binary {b:b} equals decimal ?",b
    elif kind=="hexadecimal":q,v=f"Hex {b:X} equals decimal ?",b
    elif kind=="absolute":q,v=f"Absolute value of -{a} = ?",a
    elif kind=="power":q,v=f"2 to power {c} = ?",2**c
    elif kind=="square_root":q,v=f"Square root of {a*a} = ?",a
    elif kind=="cube_root":q,v=f"Cube root of {b**3} = ?",b
    elif kind=="prime":
        n=random.choice((2,3,5,7,11,13,17,19,23,29,31));q,v=f"Next prime after {n} = ?",next(x for x in range(n+1,100) if all(x%d for d in range(2,int(x**0.5)+1)))
    elif kind=="even_odd":q,v=f"How many even numbers from 1 through {a*2}?",a
    elif kind=="divisibility":q,v=f"How many multiples of {b} from 1 to {a*b}?",a
    elif kind=="missing_number":q,v=f"{a} + ? = {a+b}",b
    elif kind=="age_difference":q,v=f"A is {a+b} years old, B is {a}. Age difference = ?",b
    elif kind=="unit_conversion":q,v=f"{a} meters = how many centimeters?",a*100
    elif kind=="angles":q,v=f"Triangle angles: {a} and {b}. Third angle = ?",180-a-b
    elif kind=="polygon_sides":q,v=f"Interior angle sum of a {b}-sided polygon = ?",(b-2)*180
    elif kind=="mean_missing":q,v=f"Mean of {a}, {a+b}, and ? is {a+b}. Missing = ?",a+2*b
    elif kind=="median":q,v=f"Median of {a}, {a+b}, {a+2*b} = ?",a+b
    elif kind=="mode":q,v=f"Mode of {a}, {a}, {b}, {c} = ?",a
    elif kind=="sets_union":q,v=f"Two disjoint sets have {a} and {b} items. Union size = ?",a+b
    else:q,v=f"Set A has {a+b} items, B has {b+c}; intersection has {b}. Intersection size = ?",b
    if not isinstance(v,int) or not q or "?" not in q:
        raise ValueError("invalid procedural question")
    offset=random.randint(1,max(3,level*5))
    wrong=v+random.choice((-1,1))*offset
    if wrong==v:wrong=v+1
    answer=random.choice(("a","b"))
    options=[str(v),str(wrong)] if answer=="a" else [str(wrong),str(v)]
    return {"id":uuid.uuid4().hex[:12],"kind":"math" if mode=="versus" else "puzzle",
            "question":q,"options":options,"answer":answer,"difficulty":level,"source":"procedural:"+kind}

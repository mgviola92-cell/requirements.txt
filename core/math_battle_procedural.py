"""Level-aware, exact-answer procedural generator for Math Battle.
The existing 15,000 fixed questions remain unchanged.
"""
import hashlib
import random

# Distinct mathematical constructions, 4 per level.
TEMPLATES = {
  1: ("signed_arithmetic", "percent_of", "average", "ratio"),
  2: ("brackets", "linear", "fraction_part", "rectangle"),
  3: ("linear_two_step", "fraction_equation", "triangle", "counting"),
  4: ("simultaneous", "quadratic_roots", "probability", "arithmetic_sequence"),
  5: ("rational_equation", "quadratic_vertex", "combinatorics", "geometry_composite"),
}

def _build(level, kind, rng):
    n = rng.randint
    if kind == "signed_arithmetic":
        a,b,c=n(15,90),n(6,45),n(3,19)
        return f"{a} - {b} + {c} × 2 = ?",a-b+2*c
    if kind == "percent_of":
        p=n(2,8)*5; base=n(8,40)*20
        return f"{p}% of {base} = ?",p*base//100
    if kind == "average":
        a,d=n(8,35),n(3,15)
        return f"Mean of {a}, {a+2*d}, {a+4*d}, {a+6*d} = ?",a+3*d
    if kind == "ratio":
        a,b,k=n(2,7),n(3,8),n(4,12)
        return f"Ratio A:B = {a}:{b}; if A = {a*k}, B = ?",b*k
    if kind == "brackets":
        a,b,c=n(8,30),n(3,13),n(3,12)
        return f"({a} + {b}) × {c} - {b*b} = ?",(a+b)*c-b*b
    if kind == "linear":
        x,a,b=n(-12,24),n(3,11),n(5,37)
        return f"Solve: {a}x + {b} = {a*x+b}; x = ?",x
    if kind == "fraction_part":
        den=n(3,12); num=n(1,den-1); k=n(5,35)
        return f"{num}/{den} of {den*k} = ?",num*k
    if kind == "rectangle":
        a,b=n(8,35),n(7,29)
        return f"Rectangle perimeter {2*(a+b)} cm, length {a} cm. Width = ?",b
    if kind == "linear_two_step":
        x,a,b,c=n(-16,25),n(3,13),n(2,11),n(2,9)
        return f"Solve: {a}(x + {b}) - {c} = {a*(x+b)-c}; x = ?",x
    if kind == "fraction_equation":
        d,a,b=n(3,12),n(2,9),n(3,16)
        x=d*n(3,23)
        return f"Solve: x/{d} + {a} = {x//d+a}; x = ?",x
    if kind == "triangle":
        base=n(6,38)*2; height=n(5,29)
        return f"Triangle area {base*height//2} cm², base {base} cm. Height = ?",height
    if kind == "counting":
        m,k=n(6,17),n(2,5)
        return f"How many {k}-digit codes using {m} symbols, repetition allowed? (Answer = ?)",m**k
    if kind == "simultaneous":
        x,y=n(-12,19),n(-10,17)
        return f"If 2x + y = {2*x+y} and x - y = {x-y}, find x = ?",x
    if kind == "quadratic_roots":
        x,y=n(-15,18),n(-14,17)
        if x==y:y+=1
        return f"If (x - ({x}))(x - ({y})) = 0, what is the SUM of both roots?",x+y
    if kind == "probability":
        red,blue=n(3,12),n(3,12)
        total=red+blue
        return f"A bag has {red} red and {blue} blue balls. With replacement, red then blue: numerator of probability over denominator {total*total} = ?",red*blue
    if kind == "arithmetic_sequence":
        a,d,nth=n(-18,30),n(3,14),n(15,38)
        return f"Arithmetic sequence starts {a}, step {d}. Term #{nth} = ?",a+(nth-1)*d
    if kind == "rational_equation":
        x,a,b=n(4,28),n(2,8),n(3,13)
        return f"Solve: (x - {b})/{a} + {b} = {(x-b)//a+b}; x = ?",x if (x-b)%a==0 else None
    if kind == "quadratic_vertex":
        h,k,a=n(-15,15),n(-30,30),n(2,7)
        return f"For y = {a}(x - ({h}))² + ({k}), y at vertex = ?",k
    if kind == "combinatorics":
        nitems=n(8,24)
        return f"Choose 3 from {nitems} distinct objects. Number of combinations = ?",nitems*(nitems-1)*(nitems-2)//6
    if kind == "geometry_composite":
        r=n(3,18); w=n(3,21);h=n(4,22)
        return f"Rectangle {w}×{h} plus square side {r}: total area = ?",w*h+r*r
    raise ValueError(kind)

def generate(level, rng=None, kind=None):
    rng = rng or random
    level = int(level)
    if level not in TEMPLATES: raise ValueError("level must be 1..5")
    kind = kind or rng.choice(TEMPLATES[level])
    if kind not in TEMPLATES[level]: raise ValueError("kind does not match level")
    for _ in range(20):
        question, answer = _build(level, kind, rng)
        if type(answer) is int and question and len(question) <= 180:
            digest = hashlib.sha256(question.encode("utf-8")).hexdigest()[:24]
            return {"id": "ADV-" + digest, "question": question, "answer": answer,
                    "level": level, "source": "math_advanced:" + kind}
    raise ValueError("failed to generate valid arithmetic question")

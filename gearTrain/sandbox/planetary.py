import sympy as sp

# variables
ws, wr, wc = sp.symbols('ws wr wc')

# teeth
Ns = 30
Nr = 70

# planetary constraint
eq1 = Ns*ws + Nr*wr - (Ns+Nr)*wc

# example case: ring fixed, sun = 100 rpm
eq2 = wr
eq3 = ws - 100

sol = sp.solve([eq1,eq2,eq3],[ws,wr,wc])

print(sol)
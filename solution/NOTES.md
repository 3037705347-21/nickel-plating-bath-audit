# Calculation notes

The bundled record is simulated from 1200 L of bath at 62.0 g/L apparent
nickel, 28.0 g/L boric acid, and 24.0 g/L chloride. The record also carries
0.12 g/L copper, a 1:1 dilution, 1800 Ah of planned charge, 94% cathode
efficiency, and 15 L of drag-out. The three titrant volumes were rounded to
0.01 mL after a seeded measurement perturbation.

Working from the stored readings gives 62.0095771 g/L apparent nickel. After
subtracting the 0.12 g/L copper equivalent, the real nickel concentration is
61.89874072949673 g/L. Boric acid is 28.009896 g/L and chloride is
24.008771600000003 g/L.

The planned deposition is 1852.681802635847 g of nickel. Compensating for
15 L of drag-out and refilling to 1200 L gives pre-shift targets of
77.51281164779397 g/L nickel, 35.44303797468354 g/L boric acid, and
30.379746835443036 g/L chloride. Drag-out removes 1162.6921747169094 g
nickel, 531.6455696202531 g boric acid, and 455.69620253164555 g chloride.

Solving the two nickel-salt equations for the deficits gives:

```text
nickel sulfate hexahydrate   56.41505459864531 kg
nickel chloride hexahydrate  26.285270151654025 kg
boric acid                    8.964593336301757 kg
total                        91.66491808660109 kg
```

The warehouse only issues 25 kg nickel sulfate, 10 kg nickel chloride, and
5 kg boric-acid bags. Rounding each exact mass upward gives 3, 3, and 2 bags,
or 75, 30, and 10 kg of commercial material. The total is 115 kg.

Using the actual packaged mass and each assay gives predicted pre-shift
concentrations of 81.66457039260354 g/L nickel, 36.30156266666667 g/L boric
acid, and 31.28011619568277 g/L chloride. These overshoot the theoretical
pre-shift targets because partial bags cannot be used.

The test file repeats the titration, Faraday, drag-out, makeup, and packaging
arithmetic through independent reference functions rather than calling the
package under test.

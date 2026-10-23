# math (`src/utils/math.py`)

Scalar helpers, stdlib only.

- `clamp(value, minimum, maximum)`: restrict value to [minimum, maximum] (ValueError if minimum > maximum).
- `lerp(start, end, t)`: linear interpolation.
- `smoothstep(edge0, edge1, x)`: smooth 0..1 easing between edges (`edge0 > edge1` gives a descending curve; equal edges raise `ValueError`).
- `normalize_angle(degrees, minimum=-180)`: wrap into `[minimum, minimum + 360)`.
- `lerp_angle(start, end, t)`: interpolate along the shortest arc (result not normalised).
- `remap(value, in_min, in_max, out_min, out_max, clamp_result=False)`: range mapping; `ValueError` if `in_min == in_max`.

```python
from src.utils import lerp
lerp(0, 10, 0.5)  # 5.0
```

Source: `src/utils/math.py`
Tests: `tests/terminal/math_test.py`.

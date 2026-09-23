# SVG Chart Mathematical Formulations

## 1. Donut Chart Geometry

Given a circle with radius $r = 70$, center $(cx, cy) = (100, 100)$, and stroke width $w = 22$:

1. **Circumference**:
   $$C = 2 \times \pi \times r \approx 439.82297$$

2. **Segment Stroke Length**:
   For each category with percentage $P_i \in [0, 100]$:
   $$\text{dash} = \frac{P_i}{100} \times C$$
   Subtract a small gap $G$ (e.g. $4\text{px}$) if there are multiple non-zero categories:
   $$\text{strokeDasharray} = (\text{dash} - G) \quad (C - (\text{dash} - G))$$

3. **Segment Offset**:
   Compute running cumulative percentage:
   $$\text{cumulativeOffset} = -\left(\frac{\sum_{k=0}^{i-1} P_k}{100}\right) \times C$$

4. **Starting Angle (12 o'clock)**:
   Add SVG transform `-rotate-90` to the `<svg>` element or `<g>` container:
   ```tsx
   <svg viewBox="0 0 200 200" className="w-full h-full transform -rotate-90">
   ```

---

## 2. Smoothed Cubic Bezier Spline Line Chart

Given $N$ points $(x_0, y_0), (x_1, y_1), \dots, (x_{n-1}, y_{n-1})$:

1. **X and Y Coordinate Scaling**:
   $$x_i = \text{paddingX} + \frac{i}{N - 1} \times \text{chartWidth}$$
   $$y_i = \text{paddingTop} + \text{chartHeight} - \left(\frac{\text{val}_i}{\text{maxVal}}\right) \times \text{chartHeight}$$

2. **Control Point Formulation**:
   For smooth transitions without sharp corners, calculate control points midway between successive points:
   $$\text{cp1x} = x_{i-1} + \frac{x_i - x_{i-1}}{2}$$
   $$\text{cp1y} = y_{i-1}$$
   $$\text{cp2x} = x_{i-1} + \frac{x_i - x_{i-1}}{2}$$
   $$\text{cp2y} = y_i$$

   Path command:
   ```typescript
   const linePath = points.reduce((acc, point, i, arr) => {
     if (i === 0) return `M ${point.x},${point.y}`;
     const prev = arr[i - 1];
     const cp1x = prev.x + (point.x - prev.x) / 2;
     const cp1y = prev.y;
     const cp2x = prev.x + (point.x - prev.x) / 2;
     const cp2y = point.y;
     return `${acc} C ${cp1x},${cp1y} ${cp2x},${cp2y} ${point.x},${point.y}`;
   }, '');
   ```

3. **Closed Area Fill**:
   To fill the gradient area below the curve, append lines to the chart bottom:
   ```typescript
   const areaPath = `${linePath} L ${lastPoint.x},${bottomY} L ${firstPoint.x},${bottomY} Z`;
   ```

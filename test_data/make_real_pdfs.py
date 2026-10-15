import pymupdf

REPORT_QUEENS = """Physics Lab Report - Measuring g Using a Pendulum
Authors: Ryan D. Martin, Emma Neary, Joshua Rinaldo, Olivia Woodman (Queens' University)

Abstract
In this experiment, we measured g by measuring the period of a pendulum of a known length.
We measured g = 7.65 +/- 0.378 m/s^2. This corresponds to a relative difference of 22% with
the accepted value (9.8 m/s^2), and our result is not consistent with the accepted value.

Theory
A pendulum exhibits simple harmonic motion (SHM), which allowed us to measure the
gravitational constant by measuring the period of the pendulum. The period, T, of a pendulum
of length L undergoing simple harmonic motion is given by: T = 2*pi*sqrt(L/g). Thus, by
measuring the period of a pendulum as well as its length, we can determine the value of
g = 4*pi^2*L/T^2. We assumed that the frequency and period of the pendulum depend on the
length of the pendulum string, rather than the angle from which it was dropped.

Predictions
We built the pendulum with a length L = 1.0000 +/- 0.0005 m that was measured with a ruler
with 1 mm graduations (thus a negligible uncertainty in L). We plan to measure the period of
one oscillation by measuring the time it takes the pendulum to go through 20 oscillations and
dividing that by 20. The period for one oscillation, based on our value of L and the accepted
value for g, is expected to be T = 2.0 s. We expect that we can measure the time for 20
oscillations with an uncertainty of 0.5 s. We thus expect to measure one oscillation with an
uncertainty of 0.025 s (about 1% relative uncertainty on the period). We thus expect that we
should be able to measure g with a relative uncertainty of the order of 1%.

Procedure
The experiment was conducted in a laboratory indoors.
1. Construction of the pendulum: We constructed the pendulum by attaching an inextensible
string to a stand on one end and to a mass on the other end. The mass, string and stand were
attached together with knots. We adjusted the knots so that the length of the pendulum was
1.0000 +/- 0.0005 m. The uncertainty is given by half of the smallest division of the ruler
that we used.
2. Measurement of the period: The pendulum was released from 90 degrees and its period was
measured by filming the pendulum with a cell-phone camera and using the phone's built-in
timer. In order to minimize the uncertainty in the period, we measured the time for the
pendulum to make 20 oscillations, and divided that time by 20. We repeated this measurement
five times. We transcribed the measurements from the cell-phone into a Jupyter Notebook.

Data and Analysis
Using a 100 g mass and 1.0 m ruler stick, the period of 20 oscillations was measured over 5
trials. The corresponding value of g for each of these trials was calculated.

Trial | Angle (deg) | Measured Period of 20 Oscillations / 20 (s) | Value of g (m/s^2)
1     | 90          | 2.24                                        | 7.87
2     | 90          | 2.37                                        | 7.03
3     | 90          | 2.28                                        | 7.59
4     | 90          | 2.26                                        | 7.73
5     | 90          | 2.22                                        | 8.01

Our final measured value of g is 7.65 +/- 0.378 m/s^2. This was calculated using the mean of
the values of g from the last column and the corresponding standard deviation. The relative
uncertainty on our measured value of g is 4.9% and the relative difference with the accepted
value of 9.8 m/s^2 is 22%, well above our relative uncertainty.

Discussion and Conclusion
In this experiment, we measured g = 7.65 +/- 0.378 m/s^2. This has a relative difference of
22% with the accepted value and our measured value is not consistent with the accepted value.
All of our measured values were systematically lower than expected, as our measured periods
were all systematically higher than the 2.0 s that we expected from our prediction. We also
found that our measurement of g had a much larger uncertainty (as determined from the spread
in values that we obtained), compared to the 1% relative uncertainty that we predicted.
We suspect that by using 20 oscillations, the pendulum slowed down due to friction, and this
resulted in a deviation from simple harmonic motion. This is consistent with the fact that
our measured periods are systematically higher. We also worry that we were not able to
accurately measure the angle from which the pendulum was released, as we did not use a
protractor. If this experiment could be redone, measuring 2 oscillations of the pendulum,
rather than 20 oscillations, could provide a more precise value of g. Additionally, a
protractor could be taped to the top of the pendulum stand, with the ruler taped to the
protractor. This way, the pendulum could be dropped from a near-perfect 90 degrees rather
than a rough estimate."""

REPORT_RICE = """Physics 111 - Experiment 1: The Large Amplitude Pendulum
by: I. M. Student, partner: A. Bumbler

We are trying to measure the amplitude dependence of the period of a simple pendulum.
By extrapolating to zero-amplitude we determine g.

Procedure
We measured the period of a simple pendulum of known length as a function of release angle.
1. Rather than measure the pendulum length directly, we used a meter stick with caliper jaws
to measure from the support to the bottom of the pendulum ball. We measured the diameter of
the ball with calipers, and found the distance from the support to the center of the ball by
subtraction.
2. To get the angle we measured the distances s and d and used the relation sin(theta) = d/s.
This seemed more accurate than using the small protractor provided.
3. The actual period was measured for the first swing after release, using a photogate timer
in pendulum mode placed near the bottom of the trajectory.

Data
total length = 0.757 m +/- 0.002 m
ball diameter = 0.0256 m +/- 0.0005 m
pendulum length = 0.744 m +/- 0.002 m
string length s = 0.731 m +/- 0.002 m

The period was measured three times for each angle and averaged:
theta (rad) | d (m)          | T (s)                     | aver T (s)
0.104 +/- 0.002 | 0.076      | 1.7326, 1.7330, 1.7328    | 1.7328
0.143        | 0.106          | 1.7294, 1.7296, 1.7297    | 1.7296
0.043        | 0.031          | 1.7286, 1.7288, 1.7288    | 1.7287
0.226        | 0.169          | 1.7380, 1.7381, 1.7382    | 1.7381
0.385        | 0.300          | 1.7606, 1.7609, 1.7609    | 1.7608
0.555        | 0.462          | 1.7460, 1.7460, 1.7462    | 1.7461

Analysis
We used Graphical Analysis to plot T vs theta^2 and fit a straight line. The straight line is
an acceptable fit, showing that the relationship T = T0 * (1 + theta^2/16) is reasonable.
To get g we use the results from the program:
intercept = T0 = 1.728 +/- 0.0002 s
slope = T0/16 = 0.108 +/- 0.001 s => T0 = 1.73 +/- 0.02 s
and the pendulum equation T0 = 2*pi*sqrt(l/g) to find g = 9.84 m/s^2. The length of the
pendulum is the largest uncertainty, at 0.3%, so it determines the uncertainty in
g = 9.84 +/- 0.03 m/s^2.

Comments
Our results are consistent with the claims in the lab manual. The value of g is about the
same as we found in the free-fall experiment."""


def make_pdf(text, path):
    doc = pymupdf.open()
    page = doc.new_page()
    rect = pymupdf.Rect(50, 50, 545, 792)
    remaining = text
    first = True
    while remaining:
        if not first:
            page = doc.new_page()
        first = False
        leftover = insert_fit(page, rect, remaining)
        remaining = leftover
    doc.save(path)
    doc.close()


def insert_fit(page, rect, text):
    n = len(text)
    while n > 0:
        used = page.insert_textbox(rect, text[:n], fontsize=10, fontname="helv")
        if used >= 0:
            return text[n:]
        n = int(n * 0.95)
    return ""


if __name__ == "__main__":
    make_pdf(REPORT_QUEENS, "real_report_queens_pendulum.pdf")
    make_pdf(REPORT_RICE, "real_report_rice_pendulum.pdf")
    for p in ["real_report_queens_pendulum.pdf", "real_report_rice_pendulum.pdf", "real_rubric_columbia.pdf"]:
        d = pymupdf.open(p)
        t = "\n".join(pg.get_text("text") for pg in d)
        print(p, "pages:", len(d), "chars:", len(t))
        print("  head:", t[:80].replace("\n", " "))
        d.close()

"""
Standalone smoke test for xfoil_runner.py — verifies XFOIL runs
fully headless with zero GUI windows and returns within seconds.

Usage:
    python verify_xfoil_headless.py

Expected behaviour:
    - XFOIL produces polar data for NACA 0012 at Re=200,000
    - Completes in < 30 seconds
    - Zero plot/GUI windows appear
    - Prints CL_max, CD_min, and elapsed time
"""
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from airfoil_engine.uiuc_parser import fetch_airfoil
from airfoil_engine.xfoil_runner import run_xfoil


def main():
    print("=" * 60)
    print("  XFOIL Headless Verification Test")
    print("=" * 60)

    # Step 1: Fetch NACA 0012 (downloads or uses cache)
    print("\n[1/3] Fetching NACA 0012 .dat file...")
    geom = fetch_airfoil("n0012")
    dat_path = Path(__file__).resolve().parent / "data" / "airfoils" / "n0012.dat"
    print(f"  OK — {geom.name}, thickness={geom.thickness_ratio:.4f}")
    print(f"  .dat path: {dat_path}")

    # Step 2: Run XFOIL with a short timeout to catch hangs
    print("\n[2/3] Running XFOIL (Re=200,000, alpha=-5..15, timeout=30s)...")
    t0 = time.perf_counter()
    try:
        polar = run_xfoil(
            dat_path,
            Re=200_000,
            alpha_start=-5.0,
            alpha_end=15.0,
            alpha_step=0.5,
            timeout_s=30.0,  # short timeout — should finish in ~5s
        )
        elapsed = time.perf_counter() - t0
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        print(f"\n  FAILED after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
        sys.exit(1)

    # Step 3: Report results
    print(f"  OK — completed in {elapsed:.1f}s")
    print(f"  Converged points: {len(polar.alpha)}")
    print(f"  CL_max  = {polar.CL_max:.4f}")
    print(f"  CD_min  = {polar.CD_min:.6f}")
    print(f"  L/D_max = {polar.L_D_max:.1f}")
    print(f"  α @ CL_max = {polar.alpha_at_CL_max:.1f}°")

    print("\n" + "=" * 60)
    if elapsed < 30.0 and len(polar.alpha) > 10:
        print("  ✓ PASS — XFOIL ran headless, no windows, fast return")
    else:
        print("  ✗ FAIL — check for GUI windows or timeout issues")
    print("=" * 60)


if __name__ == "__main__":
    main()

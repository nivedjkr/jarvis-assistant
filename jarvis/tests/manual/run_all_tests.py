import glob
import subprocess
import sys
import os

def run_tests():
    test_files = sorted(glob.glob("test_*.py"))
    print(f"Found {len(test_files)} test files to execute:\n")

    results = []
    failed_details = []

    for f in test_files:
        print(f"Running {f}...", end=" ", flush=True)
        res = subprocess.run(
            [sys.executable, f],
            capture_output=True,
            text=True,
            timeout=120
        )
        if res.returncode == 0:
            print("[OK] PASSED")
            results.append((f, "PASSED", None))
        else:
            print("[FAIL] FAILED")
            results.append((f, "FAILED", res.returncode))
            failed_details.append((f, res.stdout, res.stderr))

    print("\n" + "="*50)
    print("TEST EXECUTION SUMMARY")
    print("="*50)
    passed_count = sum(1 for _, status, _ in results if status == "PASSED")
    failed_count = sum(1 for _, status, _ in results if status == "FAILED")
    
    for f, status, code in results:
        code_str = f" (exit code {code})" if code is not None else ""
        print(f" - {f:<30}: {status}{code_str}")

    print("-" * 50)
    print(f"Total: {len(test_files)} | Passed: {passed_count} | Failed: {failed_count}")

    if failed_details:
        print("\n" + "="*50)
        print("FAILURE DETAILS")
        print("="*50)
        for f, stdout, stderr in failed_details:
            print(f"\n--- {f} ---")
            if stdout and stdout.strip():
                print(f"STDOUT:\n{stdout.strip()}")
            if stderr and stderr.strip():
                print(f"STDERR:\n{stderr.strip()}")

if __name__ == "__main__":
    run_tests()

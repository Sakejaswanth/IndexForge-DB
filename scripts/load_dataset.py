"""
scripts/load_dataset.py
CLI tool to load and preprocess datasets as described in README.
"""

import sys
import os
import argparse

def main():
    parser = argparse.ArgumentParser(description="Dataset loader and index builder")
    parser.add_argument("--dataset", choices=["gtzan_99k", "sample"], default="gtzan_99k",
                        help="Dataset to load and preprocess (default: gtzan_99k)")
    args = parser.parse_args()

    scripts_dir = os.path.dirname(os.path.abspath(__file__))

    if args.dataset == "gtzan_99k":
        csv_path = "Data/features_3_sec.csv"
        if not os.path.exists(csv_path) and not os.path.exists("data/features_3_sec.csv"):
            print(f"Dataset CSV not found at {csv_path}.")
            print("To generate synthetic sample demo indexes instead, run: python scripts/generate_sample_data.py")
            print("Or download GTZAN dataset from Kaggle as detailed in readme.md.")
            sys.exit(1)
        import preprocess
        preprocess.main()
    elif args.dataset == "sample":
        import generate_sample_data
        generate_sample_data.generate_audio_sample_data("data")
        generate_sample_data.generate_image_sample_data("data")

if __name__ == "__main__":
    main()

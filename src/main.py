import json
import os
from pipeline import run_pipeline

def main():
    
    # Run pipeline
    results = run_pipeline()
    
    # Print results
    print("Top Job Matches:")
    for result in results[:10]:  # top 10
        print(f"* {result['title']} | {result['company']} | {result['score']} | {result['decision']}")

if __name__ == "__main__":
    main()

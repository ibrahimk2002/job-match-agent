import json
import os
from pipeline.run import run_pipeline

def main():
    # Load profile
    profile_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'user_profile.json'))
    with open(profile_path, 'r') as f:
        profile = json.load(f)
    
    # Run pipeline
    results = run_pipeline(profile)
    
    # Print results
    print("Top Job Matches:")
    for result in results[:10]:  # top 10
        print(f"* {result['title']} | {result['company']} | {result['score']} | {result['decision']}")

if __name__ == "__main__":
    main()

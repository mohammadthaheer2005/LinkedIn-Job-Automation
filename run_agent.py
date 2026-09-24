import asyncio
from dotenv import load_dotenv

# Load environmental variables first
load_dotenv()

from agents.job_agent import run_linkedin_agent

def main():
    print("==================================================")
    print("💼 LinkedIn Job Automation Agent starting...")
    print("==================================================")
    try:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        # Silence third-party noisy debug loggers to keep output readable
        for logger_name in ["httpcore", "httpx", "openai", "urllib3", "playwright"]:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

        asyncio.run(run_linkedin_agent())


    except KeyboardInterrupt:
        print("\n👋 Run cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error during run: {e}")

if __name__ == "__main__":
    main()

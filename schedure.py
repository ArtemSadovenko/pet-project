import schedule
import time

def checkSubscription():
    # print("Task executed!")
    

# Schedule the correct function
schedule.every(10).seconds.do(checkSubscription)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_scheduler()

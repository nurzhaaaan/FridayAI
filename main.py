from ai_core import ask_ai
from voice_module import listen, speak

def main():
    print("Friday AI іске қосылды! 'exit' деп шығуға болады.")
    
    while True:
        user_input = listen()
        if user_input.lower() in ["exit", "шық"]:
            print("Сау болыңыз!")
            break
        
        answer = ask_ai(user_input)
        print(f"Friday: {answer}")
        speak(answer)

if __name__ == "__main__":
    main()

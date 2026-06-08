// AWT-MT 라이브 시험 샘플 — .NET(C#) 클래스 라이브러리
// 빌드: dotnet build -c Release   → bin/Release/netstandard2.0/Calculator.dll
namespace Calculator
{
    public class Calc
    {
        /// <summary>두 정수의 합.</summary>
        public int Add(int a, int b) => a + b;

        /// <summary>a / b. b=0이면 DivideByZeroException.</summary>
        public int Divide(int a, int b) => a / b;
    }
}

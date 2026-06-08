/* AWT-MT 라이브 시험 샘플 — C 네이티브 DLL
 * 빌드(MinGW): gcc -shared -o mathlib.dll mathlib.c
 * 빌드(MSVC) : cl /LD mathlib.c
 */
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

EXPORT int add(int a, int b) { return a + b; }
EXPORT int mul(int a, int b) { return a * b; }

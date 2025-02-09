#ifndef UTILS_H
#define UTILS_H

#define MAYBE(s, a) ((s) ? ((s)->a) : NULL)

#define EITHER(s1, s2, a) ((s1) ? ((s1)->a) : ((s2)->a))

#endif

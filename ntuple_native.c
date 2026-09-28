/*
 * Rdzeń natywny N-tuple (#184): ocena planszy, aktualizacja TD i przeszukanie
 * wiązką po bieżącej tacce na planszy jako 64-bitowej masce.
 *
 * Kompilowany przy pierwszym użyciu przez `ntuple_native.py` (cc -> .so, ładowany
 * przez ctypes). Liczy **bitowo to samo** co czysty Python:
 *
 * - indeks łaty: bit `i` indeksu = bit `positions[i]` planszy (`ntuple._patch_index`),
 *   tu składany z "przebiegów" — ciągłych kawałków łaty leżących na kolejnych bitach
 *   planszy (wyliczonych w Pythonie z układu łat, dowolnego);
 * - wartość: suma wag po łatach w kolejności łat, dokładnie tym algorytmem, którym
 *   liczy `sum()` CPythona (`sum_mode`: 1 = Neumaier, CPython >= 3.12; 0 = zwykłe
 *   dodawanie), zaczynając od `0 + w[0]` jak `sum(generator)` ze startem int 0;
 * - aktualizacja: `w += delta` na każdej aktywnej wadze, w kolejności łat;
 * - stan następczy: postawienie, czyszczenie pełnych wierszy i kolumn (plansza 8x8)
 *   i przejście combo jak `policies._expand`; punkty (`scoring.py`) przychodzą z
 *   Pythona jako tabele policzone tamtymi funkcjami, nie są tu przepisane.
 *
 * Kompilować bez -ffast-math i z -ffp-contract=off: kolejność i zaokrąglenia
 * dodawań muszą być dokładnie te z Pythona.
 */
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef uint64_t u64;

typedef struct {
    int32_t n_patches;
    int32_t sum_mode;
    const int32_t *run_end;   /* koniec przebiegów łaty p (wyłącznie) */
    const uint8_t *run_src;   /* przesunięcie bitu planszy */
    const uint8_t *run_dst;   /* przesunięcie w indeksie łaty */
    const uint32_t *run_mask; /* (1 << długość) - 1 */
    const int64_t *w_off;     /* początek tabeli łaty p we `w` */
    double *w;
} nt_ctx;

static inline uint32_t patch_index(const nt_ctx *c, u64 bits, int p, int *r)
{
    uint32_t idx = 0;
    int end = c->run_end[p];
    int k = *r;
    for (; k < end; k++)
        idx |= (uint32_t)((bits >> c->run_src[k]) & c->run_mask[k]) << c->run_dst[k];
    *r = k;
    return idx;
}

/* Suma jak `sum(table[i] for ...)` w CPythonie: pierwszy składnik `0 + x`
 * (PyNumber_Add int+float), dalej pętla float (Neumaier albo zwykła). */
typedef struct {
    double f;
    double comp;
} acc_t;

static inline void acc_add(acc_t *a, double x, int first, int mode)
{
    if (first) {
        a->f = 0.0 + x;
        a->comp = 0.0;
        return;
    }
    if (mode == 1) {
        double t = a->f + x;
        if (fabs(a->f) >= fabs(x))
            a->comp += (a->f - t) + x;
        else
            a->comp += (x - t) + a->f;
        a->f = t;
    } else {
        a->f += x;
    }
}

static inline double acc_result(const acc_t *a, int mode)
{
    double f = a->f;
    if (mode == 1 && a->comp != 0.0 && isfinite(a->comp))
        f += a->comp;
    return f;
}

static double value_bits(const nt_ctx *c, u64 bits)
{
    acc_t a = {0.0, 0.0};
    int r = 0;
    for (int p = 0; p < c->n_patches; p++) {
        uint32_t idx = patch_index(c, bits, p, &r);
        acc_add(&a, c->w[c->w_off[p] + idx], p == 0, c->sum_mode);
    }
    return acc_result(&a, c->sum_mode);
}

double nt_value_bits(const nt_ctx *c, u64 bits)
{
    return value_bits(c, bits);
}

void nt_indices(const nt_ctx *c, u64 bits, int32_t *out)
{
    int r = 0;
    for (int p = 0; p < c->n_patches; p++)
        out[p] = (int32_t)patch_index(c, bits, p, &r);
}

double nt_value_idx(const nt_ctx *c, const int32_t *idx)
{
    acc_t a = {0.0, 0.0};
    for (int p = 0; p < c->n_patches; p++)
        acc_add(&a, c->w[c->w_off[p] + idx[p]], p == 0, c->sum_mode);
    return acc_result(&a, c->sum_mode);
}

void nt_update(const nt_ctx *c, const int32_t *idx, double delta)
{
    for (int p = 0; p < c->n_patches; p++)
        c->w[c->w_off[p] + idx[p]] += delta;
}

/* Plansza 8x8: postawienie maski `m`, potem czyszczenie pełnych wierszy i kolumn
 * policzonych na planszy z klockiem (`Board.check_full_lines` + `clear_lines`). */
static inline u64 place_and_clear(u64 bits, u64 m, int *lines)
{
    u64 nb = bits | m;
    u64 clear = 0;
    int l = 0;
    for (int row = 0; row < 8; row++) {
        u64 rm = (u64)0xFF << (8 * row);
        if ((nb & rm) == rm) {
            clear |= rm;
            l++;
        }
    }
    for (int col = 0; col < 8; col++) {
        u64 cm = (u64)0x0101010101010101ULL << col;
        if ((nb & cm) == cm) {
            clear |= cm;
            l++;
        }
    }
    *lines = l;
    return nb & ~clear;
}

/* Postawienie `(slot, x, y)` legalne w sensie `Board.can_place_piece`? */
static inline int legal(u64 bits, u64 mask, int h, int w, int x, int y)
{
    if (x < 0 || y < 0 || x + w > 8 || y + h > 8)
        return 0;
    return ((mask << (8 * y + x)) & bits) == 0;
}

/*
 * Trening (`tools/train_ntuple._choose_action`): stany następcze wszystkich akcji
 * `acts` (trójki slot, x, y), ich wartości, liczba linii i czy plansza pusta.
 * Gdy `mode == 1`, dodatkowo wybiera akcję o największym `r_const + V` (pierwsza
 * przy remisie, jak `score > best_score`) i zapisuje jej indeksy łat do `best_idx`.
 * Zwraca numer najlepszej akcji (mode 1), 0 (mode 0) albo -1, gdy któraś akcja
 * jest nielegalna (wtedy wołający liczy po staremu).
 */
int nt_afterstates(const nt_ctx *c, u64 bits, const u64 *masks, const int32_t *hs,
                   const int32_t *ws, int n_slots, const int8_t *acts, int n, int mode,
                   double r_const, double *out_val, int32_t *out_lines, int8_t *out_empty,
                   int32_t *best_idx)
{
    int best = -1;
    double best_score = 0.0;
    u64 best_bits = 0;
    for (int k = 0; k < n; k++) {
        int s = acts[3 * k], x = acts[3 * k + 1], y = acts[3 * k + 2];
        if (s < 0 || s >= n_slots || !legal(bits, masks[s], hs[s], ws[s], x, y))
            return -1;
        int lines;
        u64 nb = place_and_clear(bits, masks[s] << (8 * y + x), &lines);
        double v = value_bits(c, nb);
        out_val[k] = v;
        out_lines[k] = lines;
        out_empty[k] = nb == 0;
        if (mode == 1) {
            double score = r_const + v;
            if (best < 0 || score > best_score) {
                best = k;
                best_score = score;
                best_bits = nb;
            }
        }
    }
    if (mode == 1) {
        if (best >= 0)
            nt_indices(c, best_bits, best_idx);
        return best;
    }
    return 0;
}

/* Indeksy łat stanu następczego jednej akcji. */
void nt_afterstate_indices(const nt_ctx *c, u64 bits, u64 mask, int x, int y, int32_t *out)
{
    int lines;
    nt_indices(c, place_and_clear(bits, mask << (8 * y + x), &lines), out);
}

/* ---- przeszukanie wiązką (`policies._tray_beam_search` z liściem N-tuple) ---- */

typedef struct {
    u64 bits;
    int64_t gain;
    double score;
    int32_t used;   /* bity slotów już postawionych */
    int32_t combo;
    int32_t cc;     /* combo_counter */
    int32_t placed;
    int32_t first;  /* slot*64 + y*8 + x pierwszej akcji albo -1 */
    int32_t pad;
} st_t;

typedef struct {
    const u64 *masks;
    const int32_t *hs;
    const int32_t *ws;
    int32_t n_slots;
    int32_t present;       /* bity slotów z klockiem (pieces[i] is not None) */
    int32_t base;          /* scoring.COMBO_COUNTER_BASE */
    int32_t c0;            /* combo korzenia */
    int32_t levels;        /* L: liczba poziomów */
    int32_t lmax;          /* tabela punktów za czyszczenie: linie 0..lmax */
    const int64_t *pp;     /* placement_points(pieces[slot]) */
    const int64_t *cp_lo;  /* clear_points(combo, lines), combo 1..L */
    const int64_t *cp_hi;  /* clear_points(combo, lines), combo c0+1..c0+L */
    int64_t fcb;           /* scoring.FULL_CLEAR_BONUS */
    int32_t path_placed;   /* 1: suma ścieżki to `placed`, 0: `gain` */
    int32_t beam;
    const int8_t *root_acts;
    int32_t n_root;        /* -1: brak listy akcji korzenia */
    int32_t error;         /* wyjście: !=0, gdy tabela punktów nie pokrywa przypadku */
} search_t;

static int expand(const nt_ctx *c, search_t *S, const st_t *st, int s, int x, int y, st_t *out)
{
    int lines;
    u64 nb = place_and_clear(st->bits, S->masks[s] << (8 * y + x), &lines);
    int64_t gained = S->pp[s];
    int32_t used = st->used | (1 << s);
    int remaining = __builtin_popcount((uint32_t)(S->present & ~used));
    int32_t combo = st->combo, cc = st->cc;
    if (lines > 0) {
        combo += 1;
        cc = S->base + remaining;
        if (lines > S->lmax) {
            S->error = 1;
            return -1;
        }
        if (combo >= S->c0 + 1 && combo <= S->c0 + S->levels)
            gained += S->cp_hi[(combo - S->c0 - 1) * (S->lmax + 1) + lines];
        else if (combo >= 1 && combo <= S->levels)
            gained += S->cp_lo[(combo - 1) * (S->lmax + 1) + lines];
        else {
            S->error = 1;
            return -1;
        }
    } else if (cc <= 1) {
        combo = 0;
        cc = S->base;
    } else {
        cc -= 1;
    }
    if (nb == 0)
        gained += S->fcb;
    out->bits = nb;
    out->used = used;
    out->combo = combo;
    out->cc = cc;
    out->gain = st->gain + gained;
    out->placed = st->placed + 1;
    out->first = st->first >= 0 ? st->first : s * 64 + y * 8 + x;
    out->score = (S->path_placed ? (double)out->placed : (double)out->gain) + value_bits(c, nb);
    return 0;
}

/* Stabilne sortowanie malejąco po `score` (jak `list.sort(reverse=True)`). */
static void msort(const st_t *cand, int32_t *idx, int32_t *tmp, int n)
{
    if (n < 2)
        return;
    int h = n / 2;
    msort(cand, idx, tmp, h);
    msort(cand, idx + h, tmp, n - h);
    int i = 0, j = h, k = 0;
    while (i < h && j < n) {
        if (cand[idx[j]].score > cand[idx[i]].score)
            tmp[k++] = idx[j++];
        else
            tmp[k++] = idx[i++];
    }
    while (i < h)
        tmp[k++] = idx[i++];
    while (j < n)
        tmp[k++] = idx[j++];
    memcpy(idx, tmp, sizeof(int32_t) * n);
}

/*
 * Zwraca liczbę stanów wiązki po ostatnim poziomie (zapisanych do `out`, najwyżej
 * `out_cap`), -2 gdy `out_cap` za małe (potrzebna liczba w `*need_out`), -1 gdy
 * akcja korzenia jest nielegalna, tabela punktów nie pokrywa przypadku albo
 * zabrakło pamięci — wtedy wołający liczy po staremu, w Pythonie.
 */
int nt_search(const nt_ctx *c, search_t *S, u64 bits, int32_t combo, int32_t cc,
              st_t *out, int out_cap, int64_t *expanded_out, int32_t *need_out)
{
    int64_t expanded = 0;
    int per_state = S->n_slots * 64 + 1;
    int n_front = 1;
    st_t *front = malloc(sizeof(st_t));
    if (!front)
        return -1;
    front[0].bits = bits;
    front[0].gain = 0;
    front[0].score = 0.0;
    front[0].used = 0;
    front[0].combo = combo;
    front[0].cc = cc;
    front[0].placed = 0;
    front[0].first = -1;
    front[0].pad = 0;
    S->error = 0;

    for (int level = 0; level < S->levels; level++) {
        int use_root = level == 0 && S->n_root >= 0;
        int cap = use_root ? S->n_root + 1 : n_front * per_state;
        if (cap < 1)
            cap = 1;
        st_t *cand = malloc(sizeof(st_t) * cap);
        int32_t *order = malloc(sizeof(int32_t) * cap * 2);
        if (!cand || !order) {
            free(cand);
            free(order);
            free(front);
            return -1;
        }
        int n = 0;
        for (int f = 0; f < n_front; f++) {
            const st_t *st = &front[f];
            int any = 0;
            if (use_root) {
                for (int k = 0; k < S->n_root; k++) {
                    int s = S->root_acts[3 * k], x = S->root_acts[3 * k + 1], y = S->root_acts[3 * k + 2];
                    if (s < 0 || s >= S->n_slots || !((S->present >> s) & 1) ||
                        !legal(st->bits, S->masks[s], S->hs[s], S->ws[s], x, y)) {
                        S->error = 1;
                        break;
                    }
                    if (expand(c, S, st, s, x, y, &cand[n]) < 0)
                        break;
                    n++;
                    any = 1;
                }
            } else {
                for (int s = 0; s < S->n_slots && !S->error; s++) {
                    if (!((S->present >> s) & 1) || ((st->used >> s) & 1))
                        continue;
                    int h = S->hs[s], w = S->ws[s];
                    for (int y = 0; y + h <= 8 && !S->error; y++)
                        for (int x = 0; x + w <= 8; x++) {
                            if ((S->masks[s] << (8 * y + x)) & st->bits)
                                continue;
                            if (expand(c, S, st, s, x, y, &cand[n]) < 0)
                                break;
                            n++;
                            any = 1;
                        }
                }
            }
            if (S->error)
                break;
            if (!any) {
                cand[n] = *st;
                cand[n].score = (S->path_placed ? (double)st->placed : (double)st->gain) +
                                value_bits(c, st->bits);
                n++;
            }
        }
        if (S->error) {
            free(cand);
            free(order);
            free(front);
            return -1;
        }
        expanded += n;
        for (int k = 0; k < n; k++)
            order[k] = k;
        msort(cand, order, order + cap, n);
        int keep = n < S->beam ? n : S->beam;
        if (keep < 0)
            keep = 0;
        st_t *nf = malloc(sizeof(st_t) * (keep > 0 ? keep : 1));
        if (!nf) {
            free(cand);
            free(order);
            free(front);
            return -1;
        }
        for (int k = 0; k < keep; k++)
            nf[k] = cand[order[k]];
        free(cand);
        free(order);
        free(front);
        front = nf;
        n_front = keep;
    }
    if (S->levels == 0) {
        for (int f = 0; f < n_front; f++)
            front[f].score = (S->path_placed ? (double)front[f].placed : (double)front[f].gain) +
                             value_bits(c, front[f].bits);
    }
    *expanded_out = expanded;
    *need_out = n_front;
    if (n_front > out_cap) {
        free(front);
        return -2;
    }
    memcpy(out, front, sizeof(st_t) * n_front);
    free(front);
    return n_front;
}

from __future__ import annotations
from .types import Type, TypeInference, Functor, Diamond, Box, TypeVar
from abc import ABC
from typing import Callable, Iterable


class TermError(Exception):
    pass


class Term(ABC):
    type:   Type
    def __repr__(self) -> str: return term_repr(self)
    def __matmul__(self, other) -> ArrowElimination: return ArrowElimination(self, other)
    def subterms(self) -> list[Term]: return subterms(self)
    def vars(self) -> Iterable[Variable]: return term_vars(self)
    def constants(self) -> Iterable[Constant]: return term_constants(self)
    def __eq__(self, other) -> bool: return isinstance(other, Term) and term_eq(self, other)
    def eta_norm(self) -> Term: return term_eta_norm(self)


TERM = TypeVar('TERM', bound=Term)


class Variable(Term):
    __match_args__ = ('type', 'index')

    def __init__(self, _type: Type, index: int):
        self.index = index
        self.type = _type


class Constant(Term):
    __match_args__ = ('type', 'index')

    def __init__(self, _type: Type, index: int):
        self.index = index
        self.type = _type


class ArrowElimination(Term):
    __match_args__ = ('function', 'argument')

    def __init__(self, function: Term, argument: Term):
        self.function = function
        self.argument = argument
        self.type = TypeInference.arrow_elim(function.type, argument.type)


class ArrowIntroduction(Term):
    __match_args__ = ('abstraction', 'body')

    def __init__(self, abstraction: Variable, body: Term):
        self.abstraction = abstraction
        self.body = body
        self.type = Functor(abstraction.type, body.type)


class DiamondIntroduction(Term):
    __match_args__ = ('decoration', 'body')

    def __init__(self, diamond: str, body: Term):
        self.decoration = diamond
        self.body = body
        self.type = Diamond(diamond, body.type)


class BoxElimination(Term):
    __match_args__ = ('decoration', 'body')

    def __init__(self, box: str | None, body: Term):
        self.type, self.decoration = TypeInference.box_elim(body.type, box)
        self.body = body


class BoxIntroduction(Term):
    __match_args__ = ('decoration', 'body')

    def __init__(self, box: str, body: Term):
        self.decoration = box
        self.body = body
        self.type = Box(box, body.type)


class DiamondElimination(Term):
    __match_args__ = ('decoration', 'body')

    def __init__(self, diamond: str | None, body: Term):
        self.type, self.decoration = TypeInference.dia_elim(body.type, diamond)
        self.body = body


########################################################################################################################
# Meta-Rules and Term Rewrites
########################################################################################################################
def substitute(term: Term, replace: Term, with_: Term) -> Term:
    TypeInference.assert_equal(replace.type, with_.type)
    if (c := term.subterms().count(replace)) != 1:
        raise TypeInference.TypeCheckError(f"Expected exactly one occurrence of {replace} in {term}, but found {c}")

    def go(_term: Term) -> Term:
        if _term == replace:
            return with_
        match _term:
            case Variable(_, _) | Constant(_, _): return _term
            case ArrowElimination(fn, arg): return ArrowElimination(go(fn), go(arg))
            case ArrowIntroduction(abst, body): return ArrowIntroduction(go(abst), go(body))
            case DiamondIntroduction(dia, body): return DiamondIntroduction(dia, go(body))
            case BoxElimination(box, body): return BoxElimination(box, go(body))
            case BoxIntroduction(box, body): return BoxIntroduction(box, go(body))
            case DiamondElimination(dia, body): return DiamondElimination(dia, go(body))
    return go(term)


def subterms(term: Term) -> list[Term]:
    match term:
        case Variable(_, _) | Constant(_, _): return [term]
        case ArrowElimination(fn, arg): return [term, *fn.subterms(), *arg.subterms()]
        case ArrowIntroduction(_, body): return [term, *body.subterms()]
        case DiamondIntroduction(_, body): return [term, *body.subterms()]
        case BoxElimination(_, body): return [term, *body.subterms()]
        case BoxIntroduction(_, body): return [term, *body.subterms()]
        case DiamondElimination(_, body): return [term, *body.subterms()]


def _word_repr(idx: int) -> str: return f'c{idx}'


def needs_par(term: Term) -> bool:
    match term:
        case Variable(_, _) | Constant(_, _): return False
        case _: return True


def term_repr(term: Term,
              show_type: bool = True,
              show_intermediate_types: bool = False,
              word_repr: Callable[[int], str] = _word_repr) -> str:

    def f(_term: Term) -> str: return term_repr(_term, False, show_intermediate_types, word_repr)
    def v(_term: Term) -> str: return term_repr(_term, False, False)

    def type_hint(s: str) -> str: return f'{s} : {term.type}' if show_type ^ show_intermediate_types else s

    match term:
        case Variable(_type, index): ret = f'x{index}'
        case Constant(_type, index): ret = f'{word_repr(index)}'
        case ArrowElimination(fn, arg): ret = f'{f(fn)} ({f(arg)})' if needs_par(arg) else f'{f(fn)} {f(arg)}'
        case ArrowIntroduction(var, body): ret = f'λ{v(var)}.({f(body)})'
        case DiamondIntroduction(decoration, body): ret = f'▵{decoration}({f(body)})'
        case BoxElimination(decoration, body): ret = f'▾{decoration}({f(body)})'
        case BoxIntroduction(decoration, body): ret = f'▴{decoration}({f(body)})'
        case DiamondElimination(decoration, body): ret = f'▿{decoration}({f(body)})'
        case _: raise NotImplementedError
    return type_hint(f'({ret})' if needs_par(term) else ret)


def term_vars(term: Term) -> Iterable[Variable]:
    match term:
        case Variable(_, _): yield term
        case Constant(_, _): yield from ()
        case ArrowElimination(fn, arg):
            yield from fn.vars()
            yield from arg.vars()
        case _:
            yield from term.body.vars()  # type: ignore


def term_constants(term: Term) -> Iterable[Constant]:
    match term:
        case Variable(_, _): yield from ()
        case Constant(_, _): yield term
        case ArrowElimination(fn, arg):
            yield from fn.constants()
            yield from arg.constants()
        case _:
            yield from term.body.constants()  # type: ignore


def term_eq(left: Term, right: Term) -> bool:
    match left, right:
        case Variable(left_type, left_index), Variable(right_type, right_index):
            return left_index == right_index and left_type == right_type
        case Constant(left_type, left_index), Constant(right_type, right_index):
            return left_index == right_index and left_type == right_type
        case ArrowElimination(left_fn, left_arg), ArrowElimination(right_fn, right_arg):
            return left_fn == right_fn and left_arg == right_arg
        case ArrowIntroduction(left_var, left_body), ArrowIntroduction(right_var, right_body):
            return left_var == right_var and left_body == right_body
        case DiamondIntroduction(left_decoration, left_body), DiamondIntroduction(right_decoration, right_body):
            return left_decoration == right_decoration and left_body == right_body
        case BoxElimination(left_decoration, left_body), BoxElimination(right_decoration, right_body):
            return left_decoration == right_decoration and left_body == right_body
        case BoxIntroduction(left_decoration, left_body), BoxIntroduction(right_decoration, right_body):
            return left_decoration == right_decoration and left_body == right_body
        case DiamondElimination(left_decoration, left_body), DiamondElimination(right_decoration, right_body):
            return left_decoration == right_decoration and left_body == right_body
        case _:
            return False


# def term_eta_norm(term: Term) -> Term:
#     match term:
#         case Variable(_, _) | Constant(_, _): return term
#         case ArrowIntroduction(var, body):
        # case ArrowIntroduction(var, ArrowElimination(fn, arg)):
        #     if var == arg:
        #         return term_eta_norm(fn)
        #     return ArrowIntroduction(var, ArrowElimination(term_eta_norm(fn), arg))
        # case ArrowIntroduction(var, body): return ArrowIntroduction(var, term_eta_norm(body))
        # case ArrowElimination(fn, arg): return ArrowElimination(term_eta_norm(fn), term_eta_norm(arg))
        # case DiamondIntroduction(outer, DiamondElimination(inner, body)):
        #     if outer == inner:
        #         return term_eta_norm(body)
        #     return DiamondIntroduction(outer, DiamondElimination(inner, term_eta_norm(body)))
        # case DiamondIntroduction(outer, body): return DiamondIntroduction(outer, term_eta_norm(body))
        # case BoxElimination(outer, BoxIntroduction(inner, body)):
        #     if outer == inner:
        #         return term_eta_norm(body)
        #     return BoxElimination(outer, BoxIntroduction(inner, term_eta_norm(body)))
        # case BoxElimination(outer, body): return BoxElimination(outer, term_eta_norm(body))
        # case BoxIntroduction(outer, BoxElimination(inner, body)):
        #     if outer == inner:
        #         return term_eta_norm(body)
        #     return BoxIntroduction(outer, BoxElimination(inner, term_eta_norm(body)))
        # case BoxIntroduction(outer, body): return BoxIntroduction(outer, term_eta_norm(body))
        # case DiamondElimination(outer, DiamondIntroduction(inner, body)):
        #     if outer == inner:
        #         return term_eta_norm(body)
        #     return DiamondElimination(outer, DiamondIntroduction(inner, term_eta_norm(body)))
        # case DiamondElimination(outer, body): return DiamondElimination(outer, term_eta_norm(body))
        # case _: raise NotImplementedError
        #

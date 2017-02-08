import sys
from antlr4.Token import CommonToken
from antlr4.InputStream import InputStream
from antlr4 import FileStream, CommonTokenStream

from plsqlLexer import plsqlLexer
from plsqlParser import plsqlParser
from plsqlVisitor import plsqlVisitor

# AST -------
# TODO: Unary expressions
#       visitChildren returns Raw node if receives > result
#       _dump method for each node, starting with smallest

class AstNode:
    def __init__(self, ctx, visitor):
        _ctx = ctx

        for mapping in self._fields:
            # parse mapping for -> and indices [] -----
            k, *name = mapping.split('->')
            name = k if not name else name[0]

            # get node -----
            print(k)
            child = getattr(ctx, k, getattr(ctx, name, None))
            # when not alias needs to be called
            if callable(child): child = child()
            # when alias set on token, need to go from CommonToken -> Terminal Node
            elif isinstance(child, CommonToken):
                # giving a name to lexer rules sets it to a token,
                # rather than the terminal node corresponding to that token
                # so we need to find it in children
                child = next(filter(lambda c: getattr(c, 'symbol', None) is child, ctx.children))

            # set attr -----
            if isinstance(child, list):
                setattr(self, name, [visitor.visit(el) for el in child])
            elif child:
                setattr(self, name, visitor.visit(child))
            else:
                setattr(self, name, child)

    def _get_field_names(self):
        return [el.split('->')[-1] for el in self._fields]

    def __str__(self):
        els = [k for k in self._get_field_names() if getattr(self, k) is not None]
        return "{}: {}".format(self.__class__.__name__, ", ".join(els))

    def __repr__(self):
        field_reps = {k: repr(getattr(self, k)) for k in self._get_field_names()}
        args = ", ".join("{} = {}".format(k, v) for k, v in field_reps.items())
        return "{}({})".format(self.__class__.__name__, args)
            

class Unshaped(AstNode):
    _fields = ['arr']

    def __init__(self, ctx, arr=tuple()):
        self.arr = arr
        self._ctx = ctx

class SelectStmt(AstNode):
    _fields = ['pref', 'expr', 'into_clause', 'from_clause', 'where_clause',
               'hierarchical_query_clause', 'group_by_clause', 'model_clause']

class Identifier(AstNode):
    _fields = ['fields']

class Star(AstNode):
    def __init__(self, *args, **kwargs): pass

class AliasExpr(AstNode):
    _fields = ['expr', 'alias']

class BinaryExpr(AstNode):
    _fields = ['op', 'left', 'right']

class UnaryExpr(AstNode):
    _fields = ['op', 'unary_expression->expr']

# VISITOR -----------

class AstVisitor(plsqlVisitor):
    def visitChildren(self, node, predicate=None):
        result = self.defaultResult()
        n = node.getChildCount()
        for i in range(n):
            if not self.shouldVisitNextChild(node, result):
                return

            c = node.getChild(i)
            if predicate and not predicate(c): continue

            childResult = c.accept(self)
            result = self.aggregateResult(result, childResult)

        if len(result) == 1: return result[0]
        elif len(result) == 0: return None
        elif all(isinstance(res, str) for res in result): return " ".join(result)
        else: return Unshaped(node, result)

    def defaultResult(self):
        return list()

    def aggregateResult(self, aggregate, nextResult):
        aggregate.append(nextResult)
        return aggregate

    def visitQuery_block(self, ctx):
        return SelectStmt(ctx, self)

    def visitTerminal(self, ctx):
        return ctx.getText()

    def visitDot_id(self, ctx):
        return Identifier(ctx, self)

    def visitStar(self, ctx):
        return Star(ctx, self)

    def visitStarTable(self, ctx):
        # TODO: account for table link with '@'
        identifier = self.visit(ctx.dot_id)
        identifier.fields += Star()
        return identifier

    def visitAlias_expr(self, ctx):
        if ctx.alias:
            return AliasExpr(ctx, self)
        else:
            return self.visitChildren(ctx)

    def visitBinaryExpr(self, ctx):
        return BinaryExpr(ctx, self)
        
    def visitUnaryExpr(self, ctx):
        return UnaryExpr(ctx, self)

    #def visitIs_part(self, ctx):
    #    return ctx

    # many outer label visitors ----------------------------------------------

    # expression conds
    visitIsExpr =     visitBinaryExpr
    #visitInExpr =    visitBinaryExpr
    visitRelExpr =    visitBinaryExpr
    visitMemberExpr = visitBinaryExpr
    visitCursorExpr = visitUnaryExpr
    visitNotExpr =    visitUnaryExpr
    visitAndExpr =    visitBinaryExpr
    visitOrExpr =     visitBinaryExpr


    def visitExpression(self, ctx):
        if (ctx.left and ctx.right):
            return BinaryExpr(ctx, selef)
        elif ctx.expression:
            return UnaryExpr(ctx, self)
        else:
            return self.visitChildren(ctx)

    # simple dropping of tokens ------
    
    def visitWhere_clause(self, ctx):
        return self.visitChildren(ctx, predicate = lambda n: n is not ctx.WHERE())

    def visitFrom_clause(self, ctx):
        return  self.visitChildren(ctx, predicate = lambda n: n is not ctx.FROM())

    def visitColumn_alias(self, ctx):
        return self.visitChildren(ctx, predicate = lambda n: n is not ctx.AS())




input_stream = InputStream("""SELECT DISTINCT CURSOR (SELECT id FROM artists), artists.name as name2 FROM artists WHERE id + 1 AND name || 'greg' """)

lexer = plsqlLexer(input_stream)
token_stream = CommonTokenStream(lexer)
parser = plsqlParser(token_stream)
#tree = parser.sql_script()
ast = AstVisitor()     
select = ast.visit(parser.query_block())
#ctx = ast.visit(parser.dot_id())


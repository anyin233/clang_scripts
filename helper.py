import clang.cindex as cindex

def dump_ast_recusively(cursor: cindex.Cursor, f, depth=0):
    f.write('  ' * depth )
    f.write(f"{cursor.kind} - {cursor.spelling}\n")
    for child in cursor.get_children():
        dump_ast_recusively(child, f, depth + 1)


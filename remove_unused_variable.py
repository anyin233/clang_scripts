import json
import argparse

from dataclasses import dataclass

from clang import cindex
from clang.cindex import CursorKind

from helper import dump_ast_recusively

INPLACE_REMOVE = False

@dataclass
class VariableDeclInfo:
    cursor: cindex.Cursor
    is_used: bool = False
    
@dataclass
class FileLocation:
    line: int
    column: int
    
@dataclass
class FileRange:
    start: FileLocation
    end: FileLocation

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', type=str, required=True)
    parser.add_argument('-o', '--output', type=str)
    
    opts = parser.parse_args()
    return opts


def load_source_to_tu(source_info) -> cindex.TranslationUnit:
    file_name = source_info['file']
    target = source_info['output']
    command = source_info['command']

    args = command.replace(f"-o {target}", "")
    args = args.replace(f"-c {file_name}", "")
    args = args.split(' ')
    args = args[1:] # remove /usr/bin/cc
    # remove '' from args
    args = [arg for arg in args if arg != '']
    
    tu = cindex.TranslationUnit.from_source(file_name, args=args)
    
    return tu
    
def find_function_decl(cursor: cindex.Cursor) -> [cindex.Cursor]:
    function_decl_list = []
    for child in cursor.get_children():
        if child.kind == CursorKind.FUNCTION_DECL:
            function_decl_list.append(child)
        else:
            function_decl_list += find_function_decl(child)

def find_compound_stmt(cursor: cindex.Cursor) -> [cindex.Cursor]:
    compound_stmt_list = []
    for child in cursor.get_children():
        if child.kind == CursorKind.COMPOUND_STMT:
            compound_stmt_list.append(child)
        else:
            compound_stmt_list += find_compound_stmt(child)
    return compound_stmt_list

def find_variable_decl(cursor: cindex.Cursor) -> {str: VariableDeclInfo}:
    variable_decl_dict = {}
    for child in cursor.get_children():
        if child.kind == CursorKind.VAR_DECL:
            var_info = VariableDeclInfo(cursor=child)
            var_name = child.spelling
            variable_decl_dict[var_name] = var_info

        variable_decl_dict.update(find_variable_decl(child))
    return variable_decl_dict

def update_variable_usage(cursor: cindex.Cursor, variable_decl_dict: {str: VariableDeclInfo}):
    for child in cursor.get_children():
        if child.kind == CursorKind.DECL_REF_EXPR:
            ref_var_name = child.spelling
            if ref_var_name in variable_decl_dict:
                variable_decl_dict[ref_var_name].is_used = True
        
        update_variable_usage(child, variable_decl_dict)
    
def remove_unused_variable(filename, decls: [VariableDeclInfo]):
    remove_span = []
    for decl in decls:
        cursor = decl.cursor
        remove_span.append(FileRange(start=FileLocation(line=cursor.extent.start.line, column=cursor.extent.start.column),
                                     end=FileLocation(line=cursor.extent.end.line, column=cursor.extent.end.column)))
    
    with open(filename, 'r+') as f:
        lines = f.readlines()
        for index, line in enumerate(lines, start=1):
            for span in remove_span:
                if index == span.start.line:
                    if span.start.line == span.end.line:
                        line = line[:span.start.column - 1] + line[span.end.column:]
                    else:
                        line = line[:span.start.column - 1]
                elif index > span.start.line and index < span.end.line:
                    line = ""
                elif index == span.end.line:
                    line = line[span.end.column:]
            lines[index-1] = line

        f.seek(0)
        f.writelines(lines)
        f.truncate()

def main(opts: argparse.Namespace) -> int:
    compile_command = opts.input
    output = opts.output
    if output is None:
        INPLACE_REMOVE = True

    complie_command_list = {}
    with open(compile_command, 'r') as f:
        complie_command_list = json.load(f)

    for source_info in complie_command_list:
        tu = load_source_to_tu(source_info)
        print(tu)
        with open("test.ast", 'w') as f:
            dump_ast_recusively(tu.cursor, f)
        
        with open("test1.ast", 'w') as f:
            compound_stmts = find_compound_stmt(tu.cursor)
            all_unused_variable = []
            for compound_stmt in compound_stmts:
                var_decl = find_variable_decl(compound_stmt)
                update_variable_usage(compound_stmt, var_decl)
                for name, info in var_decl.items():
                    f.write(name)
                    f.write(f" - {info}\n")
                unused_variable = [decl for _, decl in var_decl.items() if decl.is_used == False]
                all_unused_variable += unused_variable
                f.write("\n\n")
            remove_unused_variable(source_info['file'], all_unused_variable)
                
    
if __name__ == "__main__":

    opts = parse_args() 
    exit_code = main(opts)    
    exit(exit_code)
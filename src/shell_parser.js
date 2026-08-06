/**
 * tree-sitter-bash Shell Command Parser
 *
 * Parses shell commands and extracts dependencies using tree-sitter-bash.
 * Handles complex shell syntax including if-then-else, while loops, pipes, etc.
 *
 * Usage:
 *   node src/shell_parser.js "command string"
 *
 * Output: JSON with AST and extracted dependencies
 */

const Parser = require('tree-sitter');
const Bash = require('tree-sitter-bash');

class ShellParser {
  constructor() {
    this.parser = new Parser();
    this.parser.setLanguage(Bash);
  }

  /**
   * Parse shell command string
   * @param {string} command - Shell command to parse
   * @returns {Object} Parse result with AST and success flag
   */
  parse(command) {
    try {
      const tree = this.parser.parse(command);
      return {
        success: true,
        type: 'parse_result',
        command: command,
        text: tree.rootNode.text,
        error: null
      };
    } catch (error) {
      return {
        success: false,
        type: 'parse_result',
        command: command,
        text: null,
        error: error.message
      };
    }
  }

  /**
   * Extract input/output files from command
   * @param {string} command - Shell command
   * @returns {Object} {inputs: [], outputs: []}
   */
  extractIOFiles(command) {
    const tree = this.parser.parse(command);
    const inputs = [];
    const outputs = [];

    this._walkAST(tree.rootNode, (node) => {
      // Redirect operators: < > >>
      if (node.type === 'redirect') {
        let operator = '';
        let target = '';

        for (let child of node.children) {
          if (child.type === 'redirect_operator') {
            operator = child.text;
          } else if (child.type === 'word' || child.type === 'simple_expansion') {
            target = child.text;
          }
        }

        if (['<'].includes(operator) && target) {
          inputs.push(target);
        } else if (['>', '>>'].includes(operator) && target) {
          outputs.push(target);
        }
      }
    });

    return {
      inputs: [...new Set(inputs)],
      outputs: [...new Set(outputs)]
    };
  }

  /**
   * Extract control flow (if/while/for statements)
   * @param {string} command
   * @returns {Object} Control flow information
   */
  extractControlFlow(command) {
    const tree = this.parser.parse(command);
    const ifStatements = [];
    const whileLoops = [];
    const forLoops = [];

    this._walkAST(tree.rootNode, (node) => {
      if (node.type === 'if_statement') {
        const then_body = [];
        const else_body = [];
        let condition = '';

        for (let child of node.children) {
          if (child.type === 'condition' || child.text.startsWith('[')) {
            condition = child.text;
          } else if (child.type === 'then_clause' ||
                    (child.type === 'command' && node.children[node.children.indexOf(child) - 1]?.text === 'then')) {
            then_body.push(child.text);
          } else if (child.type === 'else_clause' ||
                    (child.type === 'command' && node.children[node.children.indexOf(child) - 1]?.text === 'else')) {
            else_body.push(child.text);
          }
        }

        if (condition) {
          ifStatements.push({
            type: 'if_statement',
            condition: condition,
            then_body: then_body,
            else_body: else_body
          });
        }
      }

      if (node.type === 'while_statement' || node.type === 'while_clause') {
        let condition = '';
        const body = [];

        for (let child of node.children) {
          if (child.type === 'condition' || child.type === 'word') {
            condition = child.text;
            break;
          }
        }

        whileLoops.push({
          type: 'while_statement',
          condition: condition,
          body: body
        });
      }

      if (node.type === 'for_statement' || node.type === 'for_clause') {
        let variable = '';
        let values = '';

        forLoops.push({
          type: 'for_statement',
          variable: variable,
          values: values,
          body: []
        });
      }
    });

    return {
      if_statements: ifStatements,
      while_loops: whileLoops,
      for_loops: forLoops
    };
  }

  /**
   * Extract pipeline operations
   * @param {string} command
   * @returns {Array} Array of command sequences
   */
  extractPipelines(command) {
    const tree = this.parser.parse(command);
    const pipelines = [];

    this._walkAST(tree.rootNode, (node) => {
      if (node.type === 'pipeline') {
        const commands = [];

        for (let child of node.children) {
          if (child.type === 'command') {
            commands.push(child.text);
          }
        }

        if (commands.length > 0) {
          pipelines.push(commands);
        }
      }
    });

    return pipelines;
  }

  /**
   * Recursively walk AST and call callback for each node
   * @private
   */
  _walkAST(node, callback) {
    callback(node);
    for (let child of node.children) {
      this._walkAST(child, callback);
    }
  }
}

// Main execution
if (require.main === module) {
  const command = process.argv[2];

  if (!command) {
    console.error('Usage: node src/shell_parser.js "<command>"');
    process.exit(1);
  }

  const parser = new ShellParser();

  // Parse command
  const parseResult = parser.parse(command);
  console.log(JSON.stringify(parseResult, null, 2));

  if (parseResult.success) {
    // Extract dependencies
    const io = parser.extractIOFiles(command);
    const controlFlow = parser.extractControlFlow(command);
    const pipelines = parser.extractPipelines(command);

    const analysis = {
      type: 'analysis_result',
      io: io,
      control_flow: controlFlow,
      pipelines: pipelines,
      has_conditionals: controlFlow.if_statements.length > 0 ||
                       controlFlow.while_loops.length > 0,
      has_pipes: pipelines.length > 0
    };

    console.log(JSON.stringify(analysis, null, 2));
  }
}

module.exports = ShellParser;

"""CLI entry point for RAG evaluation."""

import argparse
import json
import sys
from pathlib import Path

from config import AppConfig
from evaluation.evaluator import RAGEvaluator


def main():
    parser = argparse.ArgumentParser(description="FAQ Chatbot RAG精度評価CLI")
    subparsers = parser.add_subparsers(dest="command", help="サブコマンド")

    # evaluate サブコマンド
    eval_parser = subparsers.add_parser("evaluate", help="精度評価を実行する")
    eval_parser.add_argument(
        "--test-cases",
        type=str,
        required=True,
        help="テストケースJSONファイルのパス",
    )
    eval_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="結果出力先JSONファイルのパス（省略時は標準出力）",
    )

    # template サブコマンド
    tmpl_parser = subparsers.add_parser("template", help="テストケーステンプレートを生成する")
    tmpl_parser.add_argument(
        "--output",
        type=str,
        default="./data/eval_template.json",
        help="テンプレート出力先パス",
    )

    # auto サブコマンド
    auto_parser = subparsers.add_parser(
        "auto", help="FAQデータからテストケースを自動生成する"
    )
    auto_parser.add_argument(
        "--output",
        type=str,
        default="./data/eval_auto.json",
        help="自動生成テストケースの出力先パス",
    )
    auto_parser.add_argument(
        "--max-per-context",
        type=int,
        default=2,
        help="コンテキストあたりの最大生成数（デフォルト: 2）",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    config = AppConfig()
    evaluator = RAGEvaluator(config)

    if args.command == "evaluate":
        test_cases_path = Path(args.test_cases)
        if not test_cases_path.exists():
            print(f"テストケースファイルが見つかりません: {test_cases_path}")
            print("テンプレートを生成します...")
            evaluator.generate_template(test_cases_path)
            print(f"テンプレートを生成しました: {test_cases_path}")
            sys.exit(0)

        result = evaluator.run_evaluation(test_cases_path)
        output_json = result.model_dump_json(indent=2)

        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json)
            print(f"結果を出力しました: {args.output}")
        else:
            print(output_json)

    elif args.command == "template":
        output_path = Path(args.output)
        evaluator.generate_template(output_path)
        print(f"テンプレートを生成しました: {output_path}")

    elif args.command == "auto":
        output_path = Path(args.output)
        count = evaluator.generate_auto(
            output_path,
            max_goldens_per_context=args.max_per_context,
        )
        print(f"{count} 件のテストケースを自動生成しました: {output_path}")
        print(f"評価を実行するには: python -m evaluation.cli evaluate --test-cases {output_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env bash

set -u

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$script_dir" || exit 1

if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' 'Не найден uv.'
  printf '%s\n' 'Установите uv: https://docs.astral.sh/uv/getting-started/installation/'
  printf '%s\n' 'Затем снова запустите этот файл.'
  printf '\nНажмите Enter для закрытия...'
  read -r
  exit 1
fi

uv sync --extra rag
exit_code=$?
if [ "$exit_code" -ne 0 ]; then
  printf '%s\n' '' 'Не удалось подготовить окружение. Сообщение об ошибке выше.'
  printf 'Нажмите Enter для закрытия...'
  read -r
  exit "$exit_code"
fi

uv run report-processor admin
exit_code=$?
if [ "$exit_code" -ne 0 ]; then
  printf '%s\n' '' 'Панель завершилась с ошибкой. Сообщение об ошибке выше.'
  printf 'Нажмите Enter для закрытия...'
  read -r
fi

exit "$exit_code"

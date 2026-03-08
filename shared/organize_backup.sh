#!/bin/bash
# organize_backup.sh — Common file backup organization module
#
# After sourcing this file:
#   get_type_dir <filename>                              → returns type directory name
#   organize_file_to_backup <source_file> <backup_root> → moves file to backup/YYYY-MM-DD/type/, returns final path

# Returns the type directory name based on file extension (documents/images/videos/audio/others)
get_type_dir() {
    local filename="$1"
    local raw_ext="${filename##*.}"
    [ "$raw_ext" = "$filename" ] && raw_ext=""
    local ext
    ext=$(printf '%s' "$raw_ext" | tr '[:upper:]' '[:lower:]')
    case "$ext" in
        pdf|doc|docx|xls|xlsx|ppt|pptx|odt|ods)
            echo "documents" ;;
        jpg|jpeg|png|gif|webp|heic|bmp|tiff)
            echo "images" ;;
        mp4|mov|avi|mkv|m4v|wmv|flv|ts)
            echo "videos" ;;
        mp3|m4a|wav|ogg|flac|webm|aac)
            echo "audio" ;;
        *)
            echo "others" ;;
    esac
}

# Move file to <backup_root>/YYYY-MM-DD/<type>/<filename>
# Usage: organize_file_to_backup <source_file> <backup_root>
# Output: final file path (stdout)
organize_file_to_backup() {
    local src="$1"
    local backup_root="${2:-${BACKUP_ROOT:-$HOME/openclaw-backup}}"
    local today
    today=$(date +%Y-%m-%d)
    local filename
    filename=$(basename "$src")
    local type_dir
    type_dir=$(get_type_dir "$filename")
    local dest_dir="$backup_root/$today/$type_dir"
    mkdir -p "$dest_dir"

    local dest="$dest_dir/$filename"
    local raw_ext="${filename##*.}"
    local ext name_no_ext
    if [ "$raw_ext" = "$filename" ]; then
        ext=""
        name_no_ext="$filename"
    else
        ext="$raw_ext"
        name_no_ext="${filename%.*}"
    fi
    local counter=1
    while [ -f "$dest" ]; do
        if [ -n "$ext" ]; then
            dest="$dest_dir/${name_no_ext}_${counter}.${ext}"
        else
            dest="$dest_dir/${filename}_${counter}"
        fi
        counter=$((counter + 1))
    done

    mv "$src" "$dest"
    echo "$dest"
}

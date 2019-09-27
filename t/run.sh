cd "$(dirname "${BASH_SOURCE[0]}")"

pass=0
fail=0

for dir in *; do
    [ -d "$dir" ] || continue
    # run general checks
    for file in test*.sh; do
        [ -f "$file" ] || continue
        out=$(bash -e "$file" "$dir" 2>&1)
        if [ $? -eq 0 ] ; then
            : $((pass++))
            echo "P:$dir $file"
        else
            : $((fail++))
            echo "F-$dir $file:$out"
        fi
    done

    # run product specific checks
    for file in "$dir"/test*.sh; do
        [ -f "$file" ] || continue
        out=$(bash -e "$file" 2>&1)
        if [ $? -eq 0 ] ; then
            : $((pass++))
            echo "P:$file"
        else
            : $((fail++))
            echo "F-$file:$out"
        fi
    done
done

( exit $fail )

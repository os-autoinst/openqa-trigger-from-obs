cd "$(dirname "${BASH_SOURCE[0]}")"

pass=0
fail=0

for dir in *bs/*; do
    [ -d "$dir" ] || continue

    for subdir in $dir/*/; do
        # if no subdir - execute body only once
        [ -d "$subdir" ] || subdir=$dir

        # run general checks
        for file in test*.sh; do
            [ -f "$file" ] || continue
           out=$(bash -e "$file" "$subdir" 2>&1)
            if [ $? -eq 0 ] ; then
                : $((pass++))
                echo "P:$subdir $file"
            else
                : $((fail++))
                echo "F-$subdir $file:$out"
            fi
        done
        # if no subdir - execute body only once
        [ "$subdir" != "$dir" ] || break
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

( exit $fail  )

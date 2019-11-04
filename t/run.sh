cd "$(dirname "${BASH_SOURCE[0]}")"

pass=0
fail=0

for dir in *; do
    [ -d "$dir" ] || continue
    [ "$dir" != docker ] || continue
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

(
dockerfail=0 
cd docker
for t in *.sh; do
    [ -x "$t" ] || continue
    ./$t
    if [ $? -eq 0 ] ; then
        echo "P:$t"
    else
        : $((dockerfail++))
        echo "F-$t"
    fi
done
exit $dockerfail
)
dockerfail=$?
( exit $((fail + dockerfail))  )
